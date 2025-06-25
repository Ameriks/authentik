"""External logout stage API serializer"""

from rest_framework import serializers
from rest_framework.viewsets import ModelViewSet

from authentik.core.api.used_by import UsedByMixin
from authentik.flows.api.stages import StageSerializer
from authentik.stages.external_logout.models import ExternalLogoutStage


class ExternalLogoutStageSerializer(StageSerializer):
    """ExternalLogoutStage Serializer"""

    class Meta:
        model = ExternalLogoutStage
        fields = StageSerializer.Meta.fields + [
            "logout_url_template",
            "http_method",
            "additional_headers",
            "request_body_template",
            "global_logout",
            "request_timeout",
            "ignore_errors",
            "revoke_tokens",
        ]
        extra_kwargs = {
            "logout_url_template": {"allow_blank": True},
            "request_body_template": {"allow_blank": True},
            "additional_headers": {"required": False},
        }

    def validate_additional_headers(self, value):
        """Validate that additional_headers is a valid dictionary"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Additional headers must be a valid JSON object")

        # Validate header names and values
        for key, val in value.items():
            if not isinstance(key, str) or not isinstance(val, str):
                raise serializers.ValidationError(
                    "Header names and values must be strings"
                )

        return value

    def validate_request_timeout(self, value):
        """Validate request timeout is reasonable"""
        if value < 1 or value > 300:
            raise serializers.ValidationError(
                "Request timeout must be between 1 and 300 seconds"
            )
        return value

    def validate_logout_url_template(self, value):
        """Validate logout URL template format"""
        if not value:
            return value

        # Basic URL validation - should start with http:// or https://
        if not (value.startswith("http://") or value.startswith("https://")):
            raise serializers.ValidationError(
                "Logout URL template must start with http:// or https://"
            )

        return value

    def validate(self, attrs):
        """Cross-field validation"""
        # If global_logout is False, we should have a logout_url_template or it should be used in a flow context
        if not attrs.get("global_logout", False) and not attrs.get("logout_url_template", ""):
            # This is just a warning - the stage can still work in flow context
            pass

        # If HTTP method is POST, request_body_template is recommended
        if attrs.get("http_method") == "POST" and not attrs.get("request_body_template", ""):
            # This is just a warning - POST can work without body
            pass

        return super().validate(attrs)


class ExternalLogoutStageViewSet(UsedByMixin, ModelViewSet):
    """ExternalLogoutStage Viewset"""

    queryset = ExternalLogoutStage.objects.all()
    serializer_class = ExternalLogoutStageSerializer
    filterset_fields = [
        "name",
        "global_logout",
        "http_method",
        "ignore_errors",
        "revoke_tokens",
    ]
    search_fields = ["name"]
    ordering = ["name"]
