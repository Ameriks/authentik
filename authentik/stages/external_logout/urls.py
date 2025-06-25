"""External logout stage URLs"""

from authentik.stages.external_logout.api import ExternalLogoutStageViewSet

# API URL patterns - these are automatically registered by the system
api_urlpatterns = [
    ("stages/external_logout", ExternalLogoutStageViewSet),
]

# No direct URLs needed for stages
urlpatterns = []
