# apps/admissions/email_utils.py
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags


def send_application_received_email(application):
    """
    Send confirmation email when application is received
    """
    subject = f'Application Received - {application.application_number}'
    
    # Prepare context for template
    context = {
        'parent_name': application.declaration_name,
        'student_name': f"{application.first_name} {application.last_name}",
        'application_number': application.application_number,
        'applying_for_class': application.applying_for_class,
        'department': application.get_department_display(),
        'submitted_date': application.submitted_at.strftime('%B %d, %Y at %I:%M %p'),
    }
    
    # Render HTML email
    html_message = render_to_string('emails/application_received.html', context)
    plain_message = strip_tags(html_message)
    
    # Send email
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[application.declaration_name],  # You'll need to add parent email to model
        )
        email.attach_alternative(html_message, "text/html")
        email.send()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def send_application_accepted_email(application, student, exam_details):
    """
    Send acceptance email with exam details
    
    exam_details should be a dict with:
    - exam_date: str
    - exam_time: str
    - exam_location: str
    - admission_fee: str
    """
    subject = f'Admission Approved - {student.student_id}'
    
    context = {
        'parent_name': application.declaration_name,
        'student_name': f"{student.first_name} {student.last_name}",
        'student_id': student.student_id,
        'assigned_class': student.current_class.name if student.current_class else 'TBD',
        'academic_year': student.academic_year,
        'admission_date': student.admission_date.strftime('%B %d, %Y'),
        'exam_date': exam_details.get('exam_date', 'To be announced'),
        'exam_time': exam_details.get('exam_time', 'To be announced'),
        'exam_location': exam_details.get('exam_location', 'School Campus'),
        'admission_fee': exam_details.get('admission_fee', '0.00'),
    }
    
    html_message = render_to_string('emails/application_accepted.html', context)
    plain_message = strip_tags(html_message)
    
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[application.declaration_name],  # Add parent email
        )
        email.attach_alternative(html_message, "text/html")
        email.send()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def send_student_credentials_email(student, username, temporary_password, parent_email):
    """
    Send login credentials to parent
    """
    subject = f'Student Portal Access - {student.student_id}'
    
    context = {
        'parent_name': f"{student.first_name}'s Parent/Guardian",
        'student_name': f"{student.first_name} {student.last_name}",
        'username': username,
        'temporary_password': temporary_password,
        'portal_url': f"{settings.FRONTEND_URL}/auth/",
    }
    
    html_message = render_to_string('emails/student_credentials.html', context)
    plain_message = strip_tags(html_message)
    
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[parent_email],
        )
        email.attach_alternative(html_message, "text/html")
        email.send()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False