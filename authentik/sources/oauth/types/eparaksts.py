"""Eparaksts OAuth Views"""

import jwt
from datetime import datetime, timedelta
from typing import Any
from requests.exceptions import RequestException
from structlog.stdlib import get_logger
from django.shortcuts import redirect
from django.conf import settings

from authentik.sources.oauth.clients.oauth2 import OAuth2Client
from authentik.sources.oauth.types.registry import SourceType, registry
from authentik.sources.oauth.views.callback import OAuthCallback
from authentik.sources.oauth.views.redirect import OAuthRedirect

LOGGER = get_logger()


class EparakstOAuthClient(OAuth2Client):
    """Custom OAuth2 Client for Eparaksts that uses HTTP Basic auth and JSON responses"""

    def get_access_token_auth(self):
        """Use HTTP Basic auth with client credentials"""
        return (self.get_client_id(), self.get_client_secret())

    def get_access_token_args(self, callback: str, code: str) -> dict[str, Any]:
        """Get access token args for Eparaksts"""
        return {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "https://sso.emu.lv/realms/emu/broker/eparaksts/endpoint",
        }

    def get_access_token(self, **request_kwargs) -> dict[str, Any] | None:
        """Fetch access token from callback request"""
        callback = self.request.build_absolute_uri(self.callback or self.request.path)
        if not self.check_application_state():
            LOGGER.warning("Application state check failed.")
            return {"error": "State check failed."}

        code = self.get_request_arg("code", None)
        if not code:
            LOGGER.warning("No code returned by the source")
            error = self.get_request_arg("error", None)
            error_desc = self.get_request_arg("error_description", None)
            return {"error": error_desc or error or "No token received."}

        try:
            access_token_url = self.source.source_type.access_token_url or ""
            if self.source.source_type.urls_customizable and self.source.access_token_url:
                access_token_url = self.source.access_token_url

            response = self.do_request(
                "post",
                access_token_url,
                data=self.get_access_token_args(callback, code),
                auth=self.get_access_token_auth(),
                **request_kwargs,
            )
            response.raise_for_status()
        except RequestException as exc:
            LOGGER.warning(
                "Unable to fetch access token",
                exc=exc,
                response=exc.response.text if exc.response else str(exc),
            )
            return None

        try:
            return response.json()
        except ValueError as exc:
            LOGGER.warning("Failed to parse JSON response", exc=exc, response=response.text)
            return None

    def get_profile_info(self, token: dict[str, str]) -> dict[str, Any] | None:
        """Fetch user profile information from Eparaksts"""
        profile_url = self.source.source_type.profile_url or ""
        if self.source.source_type.urls_customizable and self.source.profile_url:
            profile_url = self.source.profile_url

        try:
            response = self.session.request(
                "get",
                profile_url,
                headers={
                    "Authorization": f"Bearer {token['access_token']}",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
        except RequestException as exc:
            LOGGER.warning(
                "Unable to fetch user profile",
                exc=exc,
                response=exc.response.text if exc.response else str(exc),
            )
            return None

        try:
            return response.json()
        except ValueError as exc:
            LOGGER.warning("Failed to parse JSON response", exc=exc, response=response.text)
            return None


class EparakstOAuthRedirect(OAuthRedirect):
    """Eparaksts OAuth2 Redirect"""

    def get_additional_parameters(self, source):
        params = {
            "scope": ["urn:lvrtc:fpeil:aa"],
            "ui_locales": "lv",
            "redirect_uri": "https://sso.emu.lv/realms/emu/broker/eparaksts/endpoint",
        }

        # Check if state parameter is passed in the request
        state = self.request.GET.get('state')
        if state:
            params["state"] = state

        return params


class EparakstOAuthCallback(OAuthCallback):
    """Eparaksts OAuth2 Callback with conditional redirect based on state"""

    client_class = EparakstOAuthClient

    def get_user_id(self, info: dict[str, str]) -> str:
        return info.get("sub", "")

    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to handle state-based conditional redirect"""
        # Get the state parameter from the callback
        state = request.GET.get('state')

        if state in ['sekotajs', 'sekotajsdev']:
            return self.handle_special_redirect(request, state, *args, **kwargs)

        # Default behavior for other states
        return super().dispatch(request, *args, **kwargs)

    def handle_special_redirect(self, request, state, *args, **kwargs):
        """Handle special redirect for specific states"""
        # Process OAuth callback first to get user data
        slug = kwargs.get("source_slug", "")

        print("DEBUG")
        print(request.GET)
        print(request.POST)
        print("ENDDEBUG")

        try:
            self.source = self.get_source(slug)
        except Exception:
            return self.handle_login_failure("Source not found")

        if not self.source.enabled:
            return self.handle_login_failure(f"Source {slug} is not enabled")

        client = self.get_client(self.source, callback=self.get_callback_url(self.source))

        # Get access token
        self.token = client.get_access_token()
        if self.token is None:
            return self.handle_login_failure("Could not retrieve token")
        if "error" in self.token:
            return self.handle_login_failure(self.token["error"])

        # Get profile info
        try:
            raw_info = client.get_profile_info(self.token)
            if raw_info is None:
                return self.handle_login_failure("Could not retrieve profile")
        except Exception as exc:
            return self.handle_login_failure(f"Profile retrieval failed: {str(exc)}")

        identifier = self.get_user_id(info=raw_info)
        if identifier is None:
            return self.handle_login_failure("Could not determine user ID")

        # Create JWT token with user data
        jwt_token = self.create_jwt_token(raw_info, self.token, state)

        # Get redirect URL based on state
        redirect_url = self.get_redirect_url_for_state(state, jwt_token)
        return redirect(redirect_url)

    def create_jwt_token(self, user_info: dict, token_info: dict, state: str = None) -> str:
        """Create encrypted JWT token with user data"""
        # Get secret key from settings
        secret_key = getattr(
            settings,
            'EPARAKSTS_JWT_SECRET_KEY',
            'aesheey3Veif7thaephaaesheey3Veif7thaepha'
        )

        # Prepare payload
        payload = {
            'user_id': user_info.get('sub'),
            'name': user_info.get('name'),
            'given_name': user_info.get('given_name'),
            'family_name': user_info.get('family_name'),
            'serial_number': user_info.get('serial_number'),
            'domain': user_info.get('domain'),
            'eips': user_info.get('eips'),
            'acr': user_info.get('acr'),
            'amr': user_info.get('amr'),
            'access_token': token_info.get('access_token'),
            'token_type': token_info.get('token_type'),
            'state': state,
            'exp': datetime.utcnow() + timedelta(
                minutes=15
            ),
            'iat': datetime.utcnow(),
            'iss': 'authentik-eparaksts',
            'aud': self.get_audience_for_state(state)
        }

        # Create JWT token
        algorithm = 'HS256'
        jwt_token = jwt.encode(payload, secret_key, algorithm=algorithm)
        return jwt_token

    def get_redirect_url_for_state(self, state: str, jwt_token: str) -> str:
        """Get redirect URL based on state parameter"""
        if state == 'sekotajs':
            base_url = 'https://sekotajs.emu.lv/login/'
            return f"{base_url}?token={jwt_token}"
        if state == 'sekotajsdev':
            base_url = 'http://localhost:8000/login/'
            return f"{base_url}?token={jwt_token}"
        # Default fallback
        return ""

    def get_audience_for_state(self, state: str) -> str:
        """Get JWT audience based on state parameter"""
        if state == 'sekotajs':
            return 'sekotajs.emu.lv'
        if state == 'sekotajsdev':
            return 'sekotajs.emu.dev'
        return 'unknown'

    def get_source(self, slug: str):
        """Get OAuth source by slug"""
        from authentik.sources.oauth.models import OAuthSource
        from django.shortcuts import get_object_or_404
        return get_object_or_404(OAuthSource, slug=slug)


@registry.register()
class EparakstType(SourceType):
    """Eparaksts Type definition"""

    callback_view = EparakstOAuthCallback
    redirect_view = EparakstOAuthRedirect
    verbose_name = "Eparaksts"
    name = "eparaksts"

    authorization_url = "https://eidas.eparaksts.lv/trustedx-authserver/oauth/lvrtc-eips-as"
    access_token_url = "https://eidas.eparaksts.lv/trustedx-authserver/oauth/lvrtc-eips-as/token"
    profile_url = "https://eidas.eparaksts.lv/trustedx-resources/openid/v1/users/me"

    def get_base_user_properties(self, info: dict[str, Any], **kwargs) -> dict[str, Any]:
        return {
            "username": info.get("sub"),
            "email": None,  # Eparaksts doesn't provide email
            "name": info.get("name"),
            "first_name": info.get("given_name"),
            "last_name": info.get("family_name"),
            "attributes": {
                "serial_number": info.get("serial_number"),
                "domain": info.get("domain"),
                "eips": info.get("eips"),
                "acr": info.get("acr"),
                "amr": info.get("amr"),
            },
        }
