"""Tests for external logout stage"""

import json
from unittest.mock import Mock, patch

from django.test import RequestFactory, TestCase
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore

from authentik.core.models import Application, AuthenticatedSession
from authentik.flows.models import Flow, FlowStageBinding
from authentik.flows.planner import FlowPlan, PLAN_CONTEXT_APPLICATION
from authentik.flows.views.executor import FlowExecutorView
from authentik.providers.oauth2.models import OAuth2Provider, AccessToken, RefreshToken
from authentik.stages.external_logout.models import ExternalLogoutStage
from authentik.stages.external_logout.stage import ExternalLogoutStageView

User = get_user_model()


class TestExternalLogoutStage(TestCase):
    """Test ExternalLogoutStage"""

    def setUp(self):
        self.factory = RequestFactory()

        # Create test user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        # Create test flow
        self.flow = Flow.objects.create(
            name="test-logout-flow",
            slug="test-logout-flow",
            designation="invalidation"
        )

        # Create OAuth2 provider and application
        self.provider = OAuth2Provider.objects.create(
            name="test-provider",
            client_id="test-client-id",
            client_secret="test-client-secret"
        )

        self.application = Application.objects.create(
            name="test-app",
            slug="test-app",
            provider=self.provider
        )

    def create_stage_view(self, stage_config=None, with_application=False):
        """Helper to create a stage view with mocked executor"""
        if stage_config is None:
            stage_config = {}

        stage = ExternalLogoutStage.objects.create(
            name="test-external-logout",
            **stage_config
        )

        # Create flow stage binding
        binding = FlowStageBinding.objects.create(
            target=self.flow,
            stage=stage,
            order=0
        )

        # Create request with session
        request = self.factory.get("/")
        request.user = self.user
        request.session = SessionStore()
        request.session.create()

        # Mock executor
        executor = Mock(spec=FlowExecutorView)
        executor.current_stage = stage
        executor.current_binding = binding
        executor.flow = self.flow

        # Set up plan context
        plan_context = {}
        if with_application:
            plan_context[PLAN_CONTEXT_APPLICATION] = self.application

        plan = Mock(spec=FlowPlan)
        plan.context = plan_context
        executor.plan = plan

        executor.stage_ok.return_value = Mock()

        # Create stage view
        stage_view = ExternalLogoutStageView(executor)
        stage_view.request = request

        return stage_view, stage

    def test_stage_creation(self):
        """Test basic stage creation"""
        stage = ExternalLogoutStage.objects.create(
            name="test-stage",
            logout_url_template="https://example.com/logout",
            http_method="POST",
            global_logout=False
        )

        self.assertEqual(stage.name, "test-stage")
        self.assertEqual(stage.logout_url_template, "https://example.com/logout")
        self.assertEqual(stage.http_method, "POST")
        self.assertFalse(stage.global_logout)

    def test_format_template(self):
        """Test template formatting with user data"""
        stage_view, _ = self.create_stage_view()

        template = "https://example.com/logout?user={username}&id={user_id}&email={email}"
        formatted = stage_view.format_template(template, self.user)

        expected = f"https://example.com/logout?user=testuser&id={self.user.pk}&email=test@example.com"
        self.assertEqual(formatted, expected)

    def test_format_template_with_application(self):
        """Test template formatting with application data"""
        stage_view, _ = self.create_stage_view()

        template = "https://example.com/logout?client_id={client_id}&user={username}"
        formatted = stage_view.format_template(template, self.user, self.application)

        expected = "https://example.com/logout?client_id=test-client-id&user=testuser"
        self.assertEqual(formatted, expected)

    def test_format_template_missing_placeholder(self):
        """Test template formatting with missing placeholder"""
        stage_view, _ = self.create_stage_view()

        template = "https://example.com/logout?invalid={invalid_placeholder}"
        formatted = stage_view.format_template(template, self.user)

        # Should return original template if placeholder is invalid
        self.assertEqual(formatted, template)

    def test_get_user_applications(self):
        """Test getting applications with active tokens"""
        stage_view, _ = self.create_stage_view()

        # Create access token
        AccessToken.objects.create(
            user=self.user,
            provider=self.provider,
            token="test-token",
            auth_time=stage_view.request.user.date_joined,
            revoked=False
        )

        applications = stage_view.get_user_applications()
        self.assertEqual(len(applications), 1)
        self.assertEqual(applications[0], self.application)

    def test_get_user_applications_revoked_tokens(self):
        """Test that revoked tokens don't return applications"""
        stage_view, _ = self.create_stage_view()

        # Create revoked access token
        AccessToken.objects.create(
            user=self.user,
            provider=self.provider,
            token="test-token",
            auth_time=stage_view.request.user.date_joined,
            revoked=True
        )

        applications = stage_view.get_user_applications()
        self.assertEqual(len(applications), 0)

    def test_get_current_application(self):
        """Test getting current application from flow context"""
        stage_view, _ = self.create_stage_view(with_application=True)

        current_app = stage_view.get_current_application()
        self.assertEqual(current_app, self.application)

    @patch('authentik.stages.external_logout.stage.requests.request')
    def test_make_logout_request_success(self, mock_request):
        """Test successful logout request"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        stage_config = {
            'logout_url_template': 'https://example.com/logout?user={username}',
            'http_method': 'POST',
            'request_timeout': 10
        }
        stage_view, stage = self.create_stage_view(stage_config)

        result = stage_view.make_logout_request(self.application, stage)

        self.assertTrue(result)
        mock_request.assert_called_once()

        # Verify request parameters
        call_args = mock_request.call_args
        self.assertEqual(call_args[1]['method'], 'POST')
        self.assertEqual(call_args[1]['url'], 'https://example.com/logout?user=testuser')
        self.assertEqual(call_args[1]['timeout'], 10)

    @patch('authentik.stages.external_logout.stage.requests.request')
    def test_make_logout_request_with_body(self, mock_request):
        """Test logout request with JSON body"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        stage_config = {
            'logout_url_template': 'https://example.com/logout',
            'http_method': 'POST',
            'request_body_template': '{"username": "{username}", "user_id": "{user_id}"}',
            'request_timeout': 10
        }
        stage_view, stage = self.create_stage_view(stage_config)

        result = stage_view.make_logout_request(self.application, stage)

        self.assertTrue(result)

        # Verify JSON body was sent
        call_args = mock_request.call_args
        expected_data = {"username": "testuser", "user_id": str(self.user.pk)}
        self.assertEqual(call_args[1]['json'], expected_data)

    @patch('authentik.stages.external_logout.stage.requests.request')
    def test_make_logout_request_failure(self, mock_request):
        """Test failed logout request"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_request.return_value = mock_response

        stage_config = {
            'logout_url_template': 'https://example.com/logout',
            'http_method': 'POST',
            'ignore_errors': False  # Don't ignore errors
        }
        stage_view, stage = self.create_stage_view(stage_config)

        result = stage_view.make_logout_request(self.application, stage)

        self.assertFalse(result)

    @patch('authentik.stages.external_logout.stage.requests.request')
    def test_make_logout_request_ignore_errors(self, mock_request):
        """Test logout request failure with ignore_errors=True"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_request.return_value = mock_response

        stage_config = {
            'logout_url_template': 'https://example.com/logout',
            'http_method': 'POST',
            'ignore_errors': True  # Ignore errors
        }
        stage_view, stage = self.create_stage_view(stage_config)

        result = stage_view.make_logout_request(self.application, stage)

        self.assertTrue(result)  # Should return True when ignoring errors

    def test_revoke_oauth_tokens(self):
        """Test revoking OAuth tokens"""
        stage_view, _ = self.create_stage_view()

        # Create tokens
        access_token = AccessToken.objects.create(
            user=self.user,
            provider=self.provider,
            token="test-access-token",
            auth_time=stage_view.request.user.date_joined,
            revoked=False
        )

        refresh_token = RefreshToken.objects.create(
            user=self.user,
            provider=self.provider,
            token="test-refresh-token",
            auth_time=stage_view.request.user.date_joined,
            revoked=False
        )

        # Revoke tokens for specific application
        stage_view.revoke_oauth_tokens([self.application])

        # Verify tokens were revoked
        access_token.refresh_from_db()
        refresh_token.refresh_from_db()

        self.assertTrue(access_token.revoked)
        self.assertTrue(refresh_token.revoked)

    @patch('authentik.stages.external_logout.stage.logout')
    @patch('authentik.stages.external_logout.stage.requests.request')
    def test_dispatch_single_application_logout(self, mock_request, mock_logout):
        """Test single application logout dispatch"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        stage_config = {
            'logout_url_template': 'https://example.com/logout',
            'global_logout': False,
            'revoke_tokens': True
        }
        stage_view, _ = self.create_stage_view(stage_config, with_application=True)

        # Create token for the application
        AccessToken.objects.create(
            user=self.user,
            provider=self.provider,
            token="test-token",
            auth_time=stage_view.request.user.date_joined,
            revoked=False
        )

        response = stage_view.dispatch(stage_view.request)

        # Verify logout request was made
        mock_request.assert_called_once()

        # Verify Django logout was called
        mock_logout.assert_called_once_with(stage_view.request)

        # Verify stage completed successfully
        stage_view.executor.stage_ok.assert_called_once()

    @patch('authentik.stages.external_logout.stage.logout')
    @patch('authentik.stages.external_logout.stage.requests.request')
    def test_dispatch_global_logout(self, mock_request, mock_logout):
        """Test global logout dispatch"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        stage_config = {
            'logout_url_template': 'https://example.com/logout',
            'global_logout': True,
            'revoke_tokens': True
        }
        stage_view, _ = self.create_stage_view(stage_config)

        # Create token for the application
        AccessToken.objects.create(
            user=self.user,
            provider=self.provider,
            token="test-token",
            auth_time=stage_view.request.user.date_joined,
            revoked=False
        )

        response = stage_view.dispatch(stage_view.request)

        # Verify logout request was made
        mock_request.assert_called_once()

        # Verify Django logout was called
        mock_logout.assert_called_once_with(stage_view.request)

        # Verify stage completed successfully
        stage_view.executor.stage_ok.assert_called_once()

    @patch('authentik.stages.external_logout.stage.logout')
    def test_dispatch_anonymous_user(self, mock_logout):
        """Test dispatch with anonymous user"""
        stage_view, _ = self.create_stage_view()
        stage_view.request.user = None

        response = stage_view.dispatch(stage_view.request)

        # Should skip logout and proceed
        mock_logout.assert_not_called()
        stage_view.executor.stage_ok.assert_called_once()
