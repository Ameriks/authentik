"""Eklase OAuth Views"""

import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import parse_qsl

from requests.exceptions import RequestException
from structlog.stdlib import get_logger

from authentik.lib.generators import generate_id
from authentik.sources.oauth.clients.oauth2 import (
    SESSION_KEY_OAUTH_PKCE,
    OAuth2Client,
)
from authentik.sources.oauth.types.registry import SourceType, registry
from authentik.sources.oauth.views.callback import OAuthCallback
from authentik.sources.oauth.views.redirect import OAuthRedirect

LOGGER = get_logger()


class EklaseOAuthClient(OAuth2Client):
    """Custom OAuth2 Client for Eklase that handles XML responses and form-encoded token responses"""

    def get_access_token_args(self, callback: str, code: str) -> dict[str, Any]:
        """Get access token args without PKCE - Eklase doesn't support it"""
        return {
            "redirect_uri": callback,
            "code": code,
            "grant_type": "authorization_code",
            "client_id": self.get_client_id(),
            "client_secret": self.get_client_secret(),
        }

    def get_access_token_auth(self):
        """Don't use HTTP Basic auth - send credentials in POST body"""
        return None

    def get_access_token(self, **request_kwargs) -> dict[str, Any] | None:
        """Fetch access token from callback request - handles form-encoded response"""
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

        # Check if response is JSON error first
        try:
            json_response = response.json()
            if "error" in json_response:
                LOGGER.warning("Eklase returned error", error=json_response["error"])
                return None
        except:
            pass  # Not JSON, continue with form parsing

        # Parse form-encoded response: access_token=xxx&expires=3600
        token_data = dict(parse_qsl(response.text))
        if "access_token" in token_data:
            return {
                "access_token": token_data["access_token"],
                "token_type": "Bearer",
                "expires_in": token_data.get("expires", "3600"),
            }
        return None

    def get_profile_info(self, token: dict[str, str]) -> dict[str, Any] | None:
        """Fetch user profile information - handles XML response"""
        profile_url = self.source.source_type.profile_url or ""
        if self.source.source_type.urls_customizable and self.source.profile_url:
            profile_url = self.source.profile_url

        try:
            response = self.session.request(
                "get",
                profile_url,
                params={"access_token": token["access_token"]},
                headers={"Accept": "application/json"},  # Request JSON but handle XML
            )
            response.raise_for_status()
        except RequestException as exc:
            LOGGER.warning(
                "Unable to fetch user profile",
                exc=exc,
                response=exc.response.text if exc.response else str(exc),
            )
            return None

        # Parse XML response
        try:
            # Remove BOM if present
            xml_content = response.content
            if xml_content.startswith(b'\xef\xbb\xbf'):
                xml_content = xml_content[3:]

            root = ET.fromstring(xml_content)

            # Extract data from XML structure
            person_data = {
                "id": root.findtext("ID", ""),
                "username": root.findtext("ID", ""),  # Use ID as username
                "first_name": root.findtext("FirstName", ""),
                "last_name": root.findtext("LastName", ""),
                "person_type": root.findtext("PersonType", ""),
                "school": root.findtext("School", ""),
                "class_name": root.findtext("ClassName", ""),
            }

            # Create full name
            full_name = f"{person_data['first_name']} {person_data['last_name']}".strip()

            return {
                "data": {
                    "id": person_data["id"],
                    "username": person_data["username"],
                    "name": full_name,
                    "first_name": person_data["first_name"],
                    "last_name": person_data["last_name"],
                    "person_type": person_data["person_type"],
                    "school": person_data["school"],
                    "class_name": person_data["class_name"],
                }
            }
        except ET.ParseError as exc:
            LOGGER.warning("Failed to parse XML response", exc=exc, response=response.text)
            return None


class EklaseOAuthRedirect(OAuthRedirect):
    """Eklase OAuth2 Redirect"""

    def get_additional_parameters(self, source):  # pragma: no cover
        return {
            "scope": ["openid"],  # Must be list for concatenation with additional scopes
        }


class EklaseOAuthCallback(OAuthCallback):
    """Eklase OAuth2 Callback"""

    client_class = EklaseOAuthClient

    def get_user_id(self, info: dict[str, str]) -> str:
        return info.get("data", {}).get("id", "")


@registry.register()
class EklaseType(SourceType):
    """Eklase Type definition"""

    callback_view = EklaseOAuthCallback
    redirect_view = EklaseOAuthRedirect
    verbose_name = "Eklase"
    name = "eklase"

    authorization_url = "https://my.e-klase.lv/Auth/OAuth"
    access_token_url = "https://my.e-klase.lv/Auth/OAuth/GetAccessToken"  # nosec
    profile_url = "https://my.e-klase.lv/Auth/OAuth/API/Me"

    def get_base_user_properties(self, info: dict[str, Any], **kwargs) -> dict[str, Any]:
        data = info.get("data", {})
        return {
            "username": data.get("username"),
            "email": None,  # Eklase doesn't provide email in the response
            "name": data.get("name"),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
        }
