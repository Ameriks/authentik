"""Eparaksts OAuth Views"""

from typing import Any
from requests.exceptions import RequestException
from structlog.stdlib import get_logger

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
        return {
            "scope": ["urn:lvrtc:fpeil:aa"],
            "ui_locales": "lv",
            "redirect_uri": "https://sso.emu.lv/realms/emu/broker/eparaksts/endpoint",
        }


class EparakstOAuthCallback(OAuthCallback):
    """Eparaksts OAuth2 Callback"""

    client_class = EparakstOAuthClient

    def get_user_id(self, info: dict[str, str]) -> str:
        return info.get("sub", "")


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
