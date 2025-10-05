# apps/admissions/email_utils.py
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings


def send_student_credentials_email(student, username, password):
    """
    Send login credentials to newly enrolled student
    """
    subject = f'Welcome to {settings.DEFAULT_FROM_EMAIL.split("<")[0].strip()} - Your Login Credentials'
    
    # Use the existing template or plain text
    message = f"""
Dear {student.first_name} {student.last_name},

Congratulations! You have been successfully enrolled at Excellence Academy.

Here are your login credentials:

Student ID: {student.student_id}
Username: {username}
Temporary Password: {password}

Please log in at: http://127.0.0.1:8000/auth/

IMPORTANT: You will be required to change your password on first login.

Your class: {student.current_class.name if student.current_class else 'Not assigned yet'}
Academic Year: {student.academic_year}

If you have any questions, please contact the school administration.

Best regards,
Excellence Academy Administration
    """
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[student.user.email] if student.user and student.user.email else [],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending student credentials email: {str(e)}")
        return False


def send_parent_credentials_email(parent, username, password):
    """
    Send login credentials to parent of newly enrolled student
    """
    subject = 'Excellence Academy - Parent Portal Access'
    
    # Get student names
    student_names = ', '.join([
        f"{child.first_name} {child.last_name}" 
        for child in parent.children.all()
    ])
    
    message = f"""
Dear {parent.full_name},

Welcome to Excellence Academy! Your child/children have been successfully enrolled.

Your Children: {student_names}

Here are your Parent Portal login credentials:

Username: {username}
Temporary Password: {password}

Please log in at: http://127.0.0.1:8000/auth/

Through the Parent Portal, you can:
- View your children's attendance
- Check academic performance
- View timetables
- Communicate with teachers
- Track fee payments

IMPORTANT: You will be required to change your password on first login.

If you have any questions, please contact us at {settings.EMAIL_HOST_USER}

Best regards,
Excellence Academy Administration
    """
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[parent.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending parent credentials email: {str(e)}")
        return False


def send_application_received_email(application):
    """
    Send confirmation email when application is received
    """
    subject = 'Application Received - Excellence Academy'
    
    message = f"""
Dear {application.parent_full_name},

Thank you for submitting an application to Excellence Academy for {application.first_name} {application.last_name}.

Application Number: {application.application_number}
Submitted On: {application.submitted_at.strftime('%B %d, %Y at %I:%M %p')}

Applying For: {application.applying_for_class}
Department: {application.get_department_display()}

Your application is currently under review. We will contact you within 5-7 business days regarding the next steps.

You can track your application status by contacting our admissions office or checking back with us using your application number.

Best regards,
Excellence Academy Admissions Team
Email: {settings.EMAIL_HOST_USER}
    """
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[application.parent_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending application received email: {str(e)}")
        return False


def send_exam_invitation_email(application):
    """
    Send entrance exam invitation to applicant
    """
    subject = 'Entrance Examination Invitation - Excellence Academy'
    
    message = f"""
Dear {application.parent_full_name},

Congratulations! The application for {application.first_name} {application.last_name} has been approved for the next stage.

Application Number: {application.application_number}

Your child has been scheduled for an entrance examination. Please contact our admissions office for the exam date and time.

What to bring:
- This email (printed or on phone)
- Application number
- Valid ID
- Writing materials

Location: Excellence Academy Main Campus
Contact: {settings.EMAIL_HOST_USER}

We look forward to meeting {application.first_name}!

Best regards,
Excellence Academy Admissions Team
    """
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[application.parent_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending exam invitation email: {str(e)}")
        return False


def send_application_rejection_email(application, reason=''):
    """
    Send rejection email to applicant
    """
    subject = 'Application Status Update - Excellence Academy'
    
    message = f"""
Dear {application.parent_full_name},

Thank you for your interest in Excellence Academy.

Application Number: {application.application_number}
Applicant: {application.first_name} {application.last_name}

After careful consideration, we regret to inform you that we are unable to offer admission at this time.

{f"Reason: {reason}" if reason else ""}

We encourage you to reapply in the future. If you have any questions, please contact our admissions office.

Thank you for considering Excellence Academy.

Best regards,
Excellence Academy Admissions Team
Email: {settings.EMAIL_HOST_USER}
    """
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[application.parent_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending rejection email: {str(e)}")
        return False