# apps/accounts/urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    # Working endpoints
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # JWT token endpoints (built-in)
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    #Password Reset
    path('password-reset/request/', views.request_password_reset, name='request-password-reset'),
    path('password-reset/confirm/', views.reset_password, name='reset-password'),
    path('password-change/', views.change_password, name='change-password'),
]
