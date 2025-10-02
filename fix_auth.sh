#!/bin/bash
cd ~/school-management-system/school_management
cp apps/accounts/views.py apps/accounts/views.py.backup 2>/dev/null
cp apps/dashboard/views.py apps/dashboard/views.py.backup 2>/dev/null

cat > apps/accounts/views.py << 'VIEWSEOF'
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import login, logout
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.tokens import RefreshToken

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def login_view(request):
    email_or_username = request.data.get('email_or_username')
    password = request.data.get('password')
    if not email_or_username or not password:
        return Response({'success': False, 'errors': {'general': ['Required']}}, status=400)
    from .models import User
    try:
        user = User.objects.get(email=email_or_username) if '@' in email_or_username else User.objects.get(username=email_or_username)
        if not user.check_password(password): raise User.DoesNotExist
    except User.DoesNotExist:
        return Response({'success': False, 'errors': {'general': ['Invalid']}}, status=401)
    login(request, user)
    refresh = RefreshToken.for_user(user)
    return Response({'success': True, 'tokens': {'access': str(refresh.access_token), 'refresh': str(refresh)}, 'user': {'id': user.id, 'username': user.username, 'email': user.email, 'role': user.role}})

@api_view(['POST'])
@csrf_exempt
def logout_view(request):
    logout(request)
    return Response({'success': True})
VIEWSEOF

cat > apps/dashboard/views.py << 'DASHEOF'
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required(login_url='/auth/')
def admin_dashboard(request):
    if getattr(request.user, 'role', '').lower() not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return redirect('/auth/')
    return render(request, 'admin_dashboard.html', {'user': request.user})

@login_required(login_url='/auth/')
def teacher_dashboard(request):
    if getattr(request.user, 'role', '').lower() != 'teacher' and not request.user.is_superuser:
        return redirect('/auth/')
    return render(request, 'teacher_dashboard.html', {'user': request.user})

@login_required(login_url='/auth/')
def student_dashboard(request):
    if getattr(request.user, 'role', '').lower() != 'student' and not request.user.is_superuser:
        return redirect('/auth/')
    return render(request, 'dashboard/student_dashboard.html', {'user': request.user})

@login_required(login_url='/auth/')
def parent_dashboard(request):
    if getattr(request.user, 'role', '').lower() != 'parent' and not request.user.is_superuser:
        return redirect('/auth/')
    return render(request, 'parent_dashboard.html', {'user': request.user})
DASHEOF

echo "✅ Done!"
