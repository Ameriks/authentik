"""External logout stage models"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.views import View
from rest_framework.serializers import BaseSerializer

from authentik.flows.models import Stage


class ExternalLogoutStage(Stage):
    """Stage that handles logout from external systems via HTTP requests."""

    # URL template for external logout endpoint
    # Supports placeholders: {user_id}, {username}, {email}, {session_id}
    logout_url_template = models.TextField(
        verbose_name=_("Logout URL Template"),
        help_text=_(
            "URL template for external logout endpoint. "
            "Supports placeholders: {user_id}, {username}, {email}, {session_id}, {client_id}"
        ),
        blank=True,
        default="",
    )

    # HTTP method to use for logout request
    http_method = models.CharField(
        max_length=10,
        choices=[
            ("POST", "POST"),
            ("GET", "GET"),
            ("DELETE", "DELETE"),
        ],
        default="POST",
        verbose_name=_("HTTP Method"),
        help_text=_("HTTP method to use for external logout requests"),
    )

    # Additional headers to send with the request
    additional_headers = models.JSONField(
        default=dict,
        verbose_name=_("Additional Headers"),
        help_text=_("Additional HTTP headers to send with logout requests (JSON format)"),
        blank=True,
    )

    # Request body template for POST requests
    request_body_template = models.TextField(
        verbose_name=_("Request Body Template"),
        help_text=_(
            "Template for request body (for POST requests). "
            "Supports same placeholders as URL template. Use JSON format for structured data."
        ),
        blank=True,
        default="",
    )

    # Whether to perform global logout (all connected apps) or just current app
    global_logout = models.BooleanField(
        default=False,
        verbose_name=_("Global Logout"),
        help_text=_(
            "If enabled, will logout from all applications with active tokens. "
            "If disabled, only logs out from the current application."
        ),
    )

    # Timeout for HTTP requests
    request_timeout = models.IntegerField(
        default=10,
        verbose_name=_("Request Timeout"),
        help_text=_("Timeout in seconds for external logout requests"),
    )

    # Whether to ignore HTTP errors from external systems
    ignore_errors = models.BooleanField(
        default=True,
        verbose_name=_("Ignore Errors"),
        help_text=_(
            "If enabled, HTTP errors from external systems won't prevent the logout flow. "
            "If disabled, errors will be logged but the logout will continue."
        ),
    )

    # Whether to revoke OAuth tokens
    revoke_tokens = models.BooleanField(
        default=True,
        verbose_name=_("Revoke OAuth Tokens"),
        help_text=_("Whether to revoke OAuth2 access and refresh tokens during logout"),
    )

    @property
    def serializer(self) -> type[BaseSerializer]:
        from authentik.stages.external_logout.api import ExternalLogoutStageSerializer

        return ExternalLogoutStageSerializer

    @property
    def view(self) -> type[View]:
        from authentik.stages.external_logout.stage import ExternalLogoutStageView

        return ExternalLogoutStageView

    @property
    def component(self) -> str:
        return "ak-stage-external-logout-form"

    class Meta:
        verbose_name = _("External Logout Stage")
        verbose_name_plural = _("External Logout Stages")
