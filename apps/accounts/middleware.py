# apps/accounts/middleware.py - NEW FILE
from django.shortcuts import redirect
from django.urls import reverse

class ForcePasswordChangeMiddleware:
    """
    Middleware to force users to change their password on first login
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # URLs that don't require password change
        exempt_urls = [
            reverse('change-password'),
            reverse('logout'),
            '/api/v1/auth/logout/',
            '/api/v1/auth/change-password/',
            '/auth/',
            '/static/',
            '/media/',
        ]
        
        # Check if user is authenticated and must change password
        if request.user.is_authenticated:
            if hasattr(request.user, 'must_change_password') and request.user.must_change_password:
                # Allow access to change password page and static files
                if not any(request.path.startswith(url) for url in exempt_urls):
                    # For API requests, return JSON response
                    if request.path.startswith('/api/'):
                        from django.http import JsonResponse
                        return JsonResponse({
                            'success': False,
                            'error': 'You must change your password before accessing this resource',
                            'must_change_password': True
                        }, status=403)
                    else:
                        # For web requests, redirect to change password page
                        return redirect('change-password')
        
        response = self.get_response(request)
        return response