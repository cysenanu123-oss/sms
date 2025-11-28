# apps/accounts/middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from django.http import JsonResponse

class ForcePasswordChangeMiddleware:
    """
    Middleware to force users to change their password on first login.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user

        if user.is_authenticated and getattr(user, 'must_change_password', False):
            exempt_urls = [
                reverse('password_change'),
                reverse('logout'),
                '/api/v1/auth/logout/',
                '/api/v1/auth/change-password/',
                '/auth/',
                '/admin/',
                '/static/',
                '/media/',
            ]
            if not any(request.path.startswith(url) for url in exempt_urls):
                if request.path.startswith('/api/'):
                    return JsonResponse({
                        'success': False,
                        'error': 'You must change your password before accessing this resource.',
                        'must_change_password': True
                    }, status=403)
                else:
                    return redirect('password_change')
        
        return self.get_response(request)
