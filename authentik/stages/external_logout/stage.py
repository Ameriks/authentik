"""External logout stage logic"""

import json
import logging
from typing import Any, Dict, List
from urllib.parse import urlencode

import requests
from django.contrib.auth import logout
from django.db import models
from django.http import HttpRequest, HttpResponse
from structlog.stdlib import get_logger

from authentik.core.models import Application, AuthenticatedSession
from authentik.flows.planner import PLAN_CONTEXT_APPLICATION
from authentik.flows.stage import StageView
from authentik.providers.oauth2.models import AccessToken, OAuth2Provider, RefreshToken
from authentik.stages.external_logout.models import ExternalLogoutStage

LOGGER = get_logger()


class ExternalLogoutStageView(StageView):
    """Stage that handles logout from external systems via HTTP requests"""

    def get_stage_instance(self) -> ExternalLogoutStage:
        """Get the current stage instance"""
        return self.executor.current_stage

    def get_user_applications(self) -> List[Application]:
        """Get all applications that have active tokens for the current user"""
        if not self.request.user or self.request.user.is_anonymous:
            return []

        # Get all OAuth2 providers that have active tokens for this user
        active_providers = OAuth2Provider.objects.filter(
            models.Q(accesstoken__user=self.request.user, accesstoken__revoked=False) |
            models.Q(refreshtoken__user=self.request.user, refreshtoken__revoked=False)
        ).distinct()

        # Get applications for these providers
        applications = []
        for provider in active_providers:
            if hasattr(provider, 'application') and provider.application:
                applications.append(provider.application)

        return applications

    def get_current_application(self) -> Application:
        """Get the current application from flow context"""
        if not self.executor.plan:
            return None
        return self.executor.plan.context.get(PLAN_CONTEXT_APPLICATION)

    def format_template(self, template: str, user, application: Application = None, session_id: str = None) -> str:
        """Format a template string with user and application data"""
        if not template:
            return ""

        format_data = {
            'user_id': str(user.pk) if user else '',
            'username': user.username if user else '',
            'email': user.email if user else '',
            'session_id': session_id or '',
        }

        if application and hasattr(application, 'get_provider'):
            provider = application.get_provider()
            if isinstance(provider, OAuth2Provider):
                format_data['client_id'] = provider.client_id

        try:
            return template.format(**format_data)
        except KeyError as e:
            self.logger.warning(
                "Template formatting error",
                template=template,
                error=str(e),
                available_keys=list(format_data.keys())
            )
            return template

    def make_logout_request(self, application: Application, stage: ExternalLogoutStage) -> bool:
        """Make HTTP request to external application logout endpoint"""
        if not stage.logout_url_template:
            self.logger.debug("No logout URL template configured", application=application.name)
            return True

        # Get session information
        session_id = self.request.session.session_key

        # Format the logout URL
        logout_url = self.format_template(
            stage.logout_url_template,
            self.request.user,
            application,
            session_id
        )

        if not logout_url:
            self.logger.warning("Empty logout URL after formatting", application=application.name)
            return False

        # Prepare headers
        headers = {
            'User-Agent': 'Authentik-External-Logout/1.0',
            'Content-Type': 'application/json' if stage.http_method == 'POST' else 'application/x-www-form-urlencoded'
        }

        # Add additional headers
        if stage.additional_headers:
            headers.update(stage.additional_headers)

        # Prepare request data
        data = None
        if stage.http_method == 'POST' and stage.request_body_template:
            body_content = self.format_template(
                stage.request_body_template,
                self.request.user,
                application,
                session_id
            )

            # Try to parse as JSON, fall back to string
            try:
                data = json.loads(body_content)
            except json.JSONDecodeError:
                data = body_content
                headers['Content-Type'] = 'text/plain'

        try:
            self.logger.info(
                "Making external logout request",
                application=application.name,
                url=logout_url,
                method=stage.http_method,
                user=self.request.user.username
            )

            response = requests.request(
                method=stage.http_method,
                url=logout_url,
                headers=headers,
                json=data if isinstance(data, dict) else None,
                data=data if not isinstance(data, dict) else None,
                timeout=stage.request_timeout,
                verify=True  # Always verify SSL certificates
            )

            if response.status_code < 400:
                self.logger.info(
                    "External logout request successful",
                    application=application.name,
                    status_code=response.status_code,
                    user=self.request.user.username
                )
                return True
            else:
                self.logger.warning(
                    "External logout request failed",
                    application=application.name,
                    status_code=response.status_code,
                    response_text=response.text[:500],  # Limit response text
                    user=self.request.user.username
                )
                return not stage.ignore_errors

        except requests.exceptions.Timeout:
            self.logger.error(
                "External logout request timed out",
                application=application.name,
                timeout=stage.request_timeout,
                user=self.request.user.username
            )
            return not stage.ignore_errors

        except requests.exceptions.RequestException as e:
            self.logger.error(
                "External logout request failed with exception",
                application=application.name,
                error=str(e),
                user=self.request.user.username
            )
            return not stage.ignore_errors

    def revoke_oauth_tokens(self, applications: List[Application] = None):
        """Revoke OAuth2 tokens for specified applications or all applications"""
        if not self.request.user or self.request.user.is_anonymous:
            return

        # Get providers to revoke tokens for
        if applications:
            provider_ids = []
            for app in applications:
                provider = app.get_provider()
                if isinstance(provider, OAuth2Provider):
                    provider_ids.append(provider.pk)

            if not provider_ids:
                return

            access_tokens = AccessToken.objects.filter(
                user=self.request.user,
                provider_id__in=provider_ids,
                revoked=False
            )
            refresh_tokens = RefreshToken.objects.filter(
                user=self.request.user,
                provider_id__in=provider_ids,
                revoked=False
            )
        else:
            # Revoke all tokens for user
            access_tokens = AccessToken.objects.filter(
                user=self.request.user,
                revoked=False
            )
            refresh_tokens = RefreshToken.objects.filter(
                user=self.request.user,
                revoked=False
            )

        # Revoke tokens
        access_count = access_tokens.update(revoked=True)
        refresh_count = refresh_tokens.update(revoked=True)

        self.logger.info(
            "Revoked OAuth tokens",
            user=self.request.user.username,
            access_tokens=access_count,
            refresh_tokens=refresh_count
        )

    def dispatch(self, request: HttpRequest) -> HttpResponse:
        """Handle the external logout process"""
        stage = self.get_stage_instance()

        if not request.user or request.user.is_anonymous:
            self.logger.debug("No authenticated user found, skipping external logout")
            return self.executor.stage_ok()

        success = True
        applications_to_logout = []

        if stage.global_logout:
            # Global logout - get all applications with active tokens
            applications_to_logout = self.get_user_applications()
            self.logger.info(
                "Performing global logout",
                user=request.user.username,
                application_count=len(applications_to_logout)
            )
        else:
            # Single application logout
            current_app = self.get_current_application()
            if current_app:
                applications_to_logout = [current_app]
                self.logger.info(
                    "Performing single application logout",
                    user=request.user.username,
                    application=current_app.name
                )

        # Make logout requests to external systems
        for application in applications_to_logout:
            if not self.make_logout_request(application, stage):
                success = False

        # Revoke OAuth tokens if configured
        if stage.revoke_tokens:
            if stage.global_logout:
                self.revoke_oauth_tokens()  # Revoke all tokens
            else:
                self.revoke_oauth_tokens(applications_to_logout)  # Revoke specific app tokens

        # Log out from Authentik session
        self.logger.debug(
            "Logging out from Authentik",
            user=request.user.username,
            flow_slug=self.executor.flow.slug,
        )
        logout(request)

        if not success and not stage.ignore_errors:
            self.logger.error(
                "External logout failed for some applications",
                user=request.user.username
            )
            # You might want to return an error response here
            # For now, we continue with the flow

        return self.executor.stage_ok()
