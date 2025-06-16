"""Language URL Parameter Middleware for authentik"""

from collections.abc import Callable
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils import translation
from django.utils.translation import get_supported_language_variant


class LanguageParameterMiddleware:
    """Middleware to handle language URL parameters and set language cookies.
    
    This middleware checks for ?lang=<language_code> or ?locale=<language_code> URL parameters and:
    1. Sets the appropriate language cookie if the language is supported
    2. Activates the translation for the current request
    
    Supported languages are determined by the available locale directories.
    """

    get_response: Callable[[HttpRequest], HttpResponse]

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Check for language parameter in URL (support both 'lang' and 'locale')
        lang_param = request.GET.get('lang') or request.GET.get('locale')
        
        if lang_param:
            # Validate the language code against supported languages
            try:
                # Get supported language variant (handles cases like 'en-us' -> 'en')
                supported_lang = get_supported_language_variant(lang_param)
                if supported_lang:
                    # Activate the language for this request
                    translation.activate(supported_lang)
                    request.LANGUAGE_CODE = supported_lang
                    
                    # Get the response first
                    response = self.get_response(request)
                    
                    # Set the language cookie on the response
                    # Use the same secure/samesite logic as SessionMiddleware
                    from authentik.root.middleware import SessionMiddleware
                    secure = SessionMiddleware.is_secure(request)
                    same_site = "None" if secure else "Lax"
                    
                    response.set_cookie(
                        settings.LANGUAGE_COOKIE_NAME,
                        supported_lang,
                        max_age=settings.LANGUAGE_COOKIE_AGE if hasattr(settings, 'LANGUAGE_COOKIE_AGE') else 365 * 24 * 60 * 60,  # 1 year default
                        domain=getattr(settings, 'LANGUAGE_COOKIE_DOMAIN', None),
                        path=getattr(settings, 'LANGUAGE_COOKIE_PATH', '/'),
                        secure=secure,
                        httponly=getattr(settings, 'LANGUAGE_COOKIE_HTTPONLY', False),
                        samesite=same_site,
                    )
                    
                    return response
                    
            except LookupError:
                # Language not supported, fall through to default handling
                pass
        
        # No language parameter or unsupported language, proceed normally
        response = self.get_response(request)
        return response