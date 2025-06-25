"""External logout stage app config"""

from django.apps import AppConfig


class AuthentikStagesExternalLogoutConfig(AppConfig):
    """External logout stage app config"""

    name = "authentik.stages.external_logout"
    label = "authentik_stages_external_logout"
    verbose_name = "Authentik Stages External Logout"
    default_auto_field = "django.db.models.BigAutoField"
