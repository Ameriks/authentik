"""Language Parameter Middleware tests"""

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.test import TestCase, RequestFactory
from django.utils import translation

from authentik.root.locale_middleware import LanguageParameterMiddleware


class TestLanguageParameterMiddleware(TestCase):
    """Test Language Parameter Middleware"""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = LanguageParameterMiddleware(lambda request: HttpResponse())

    def test_no_language_parameter(self):
        """Test request without language parameter proceeds normally"""
        request = self.factory.get('/')
        response = self.middleware(request)
        
        self.assertEqual(response.status_code, 200)
        # Should not set language cookie
        self.assertNotIn(settings.LANGUAGE_COOKIE_NAME, response.cookies)

    def test_supported_language_parameter(self):
        """Test request with supported language parameter sets cookie and activates language"""
        request = self.factory.get('/?lang=fr')
        response = self.middleware(request)
        
        self.assertEqual(response.status_code, 200)
        # Should set language cookie
        self.assertIn(settings.LANGUAGE_COOKIE_NAME, response.cookies)
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, 'fr')
        
        # Should set LANGUAGE_CODE on request
        self.assertEqual(request.LANGUAGE_CODE, 'fr')

    def test_latvian_language_parameter(self):
        """Test request with Latvian language parameter"""
        request = self.factory.get('/?lang=lv')
        response = self.middleware(request)
        
        self.assertEqual(response.status_code, 200)
        # Should set language cookie
        self.assertIn(settings.LANGUAGE_COOKIE_NAME, response.cookies)
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, 'lv')
        
        # Should set LANGUAGE_CODE on request
        self.assertEqual(request.LANGUAGE_CODE, 'lv')

    def test_unsupported_language_parameter(self):
        """Test request with unsupported language parameter is ignored"""
        request = self.factory.get('/?lang=xyz')
        response = self.middleware(request)
        
        self.assertEqual(response.status_code, 200)
        # Should not set language cookie for unsupported language
        self.assertNotIn(settings.LANGUAGE_COOKIE_NAME, response.cookies)
        # Should not set LANGUAGE_CODE on request
        self.assertFalse(hasattr(request, 'LANGUAGE_CODE'))

    def test_language_code_normalization(self):
        """Test that language codes are normalized (e.g., zh-Hans -> zh-hans)"""
        request = self.factory.get('/?lang=zh-Hans')
        response = self.middleware(request)
        
        self.assertEqual(response.status_code, 200)
        # Should set normalized language code in cookie
        if settings.LANGUAGE_COOKIE_NAME in response.cookies:
            cookie_value = response.cookies[settings.LANGUAGE_COOKIE_NAME].value
            # Should be normalized to lowercase
            self.assertTrue(cookie_value in ['zh-hans', 'zh'])

    def test_cookie_attributes(self):
        """Test that language cookie has correct attributes"""
        request = self.factory.get('/?lang=fr')
        # Mock secure connection
        request.META['HTTP_X_FORWARDED_PROTO'] = 'https'
        response = self.middleware(request)
        
        self.assertEqual(response.status_code, 200)
        cookie = response.cookies[settings.LANGUAGE_COOKIE_NAME]
        
        # Check cookie attributes
        self.assertEqual(cookie.value, 'fr')
        self.assertEqual(cookie['path'], getattr(settings, 'LANGUAGE_COOKIE_PATH', '/'))
        # Should have appropriate security settings
        self.assertIn('samesite', cookie.output().lower())

    def test_multiple_parameters(self):
        """Test request with multiple parameters including language"""
        request = self.factory.get('/?other=value&lang=lv&more=data')
        response = self.middleware(request)
        
        self.assertEqual(response.status_code, 200)
        # Should still process language parameter correctly
        self.assertIn(settings.LANGUAGE_COOKIE_NAME, response.cookies)
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, 'lv')

    def test_case_insensitive_language_codes(self):
        """Test that language codes work case-insensitively"""
        test_cases = ['FR', 'Fr', 'fR', 'fr']
        
        for lang_code in test_cases:
            with self.subTest(lang_code=lang_code):
                request = self.factory.get(f'/?lang={lang_code}')
                response = self.middleware(request)
                
                # Should normalize to lowercase and work
                if settings.LANGUAGE_COOKIE_NAME in response.cookies:
                    cookie_value = response.cookies[settings.LANGUAGE_COOKIE_NAME].value
                    self.assertEqual(cookie_value.lower(), 'fr')