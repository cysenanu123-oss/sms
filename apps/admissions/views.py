# apps/admissions/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .models import StudentApplication
from .serializers import StudentApplicationSerializer
from .email_utils import send_application_received_email


@api_view(['POST'])
@permission_classes([AllowAny])
def submit_application(request):
    """
    Handle student application form submission
    """
    try:
        serializer = StudentApplicationSerializer(data=request.data)
        
        if serializer.is_valid():
            application = serializer.save()
            
            # Send confirmation email
            email_sent = send_application_received_email(application)
            
            return Response({
                'success': True,
                'message': 'Application submitted successfully',
                'application_number': application.application_number,
                'email_sent': email_sent,
                'data': {
                    'application_number': application.application_number,
                    'student_name': f"{application.first_name} {application.last_name}",
                    'department': application.get_department_display(),
                    'submitted_at': application.submitted_at.isoformat()
                }
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'error': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)