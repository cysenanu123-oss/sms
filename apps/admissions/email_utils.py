# apps/admissions/email_utils.py
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings


def send_student_credentials_email(student, username, password, parent_email):
    """
    Send login credentials to parent about the newly enrolled student
    
    Args:
        student: Student object
        username: Student's username
        password: Student's temporary password
        parent_email: Parent's email to send credentials to
    """
    subject = f'Welcome to Excellence Academy - Student Login Credentials for {student.first_name}'
    
    message = f"""
Dear Parent/Guardian,

Congratulations! {student.first_name} {student.last_name} has been successfully enrolled at Excellence Academy.

STUDENT LOGIN CREDENTIALS:

Student ID: {student.student_id}
Username: {username}
Temporary Password: {password}

Login URL: http://127.0.0.1:8000/auth/

Class: {student.current_class.name if student.current_class else 'Not assigned yet'}
Academic Year: {student.academic_year}

IMPORTANT SECURITY NOTICE:
⚠️ The student will be required to change this password on first login.
⚠️ Please keep these credentials secure and share them only with your child.

Through the student portal, your child can:
- View class schedules and timetables
- Access learning resources
- Check assignments and homework
- View grades and report cards

If you have any questions, please contact the school administration.

Best regards,
Excellence Academy Administration
Email: {settings.EMAIL_HOST_USER}
    """
    
    try:
        result = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[parent_email],
            fail_silently=False,
        )
        print(f"✅ Student credentials email sent to {parent_email}. Result: {result}")
        return True
    except Exception as e:
        print(f"❌ Error sending student credentials email: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def send_parent_credentials_email(parent, username, password, student_name):
    """
    Send login credentials to parent for parent portal access
    
    Args:
        parent: Parent object
        username: Parent's username
        password: Parent's temporary password
        student_name: Name of the student (for context)
    """
    subject = 'Excellence Academy - Parent Portal Access Credentials'
    
    # Get all children names
    student_names = ', '.join([
        f"{child.first_name} {child.last_name}" 
        for child in parent.children.all()
    ])
    
    message = f"""
Dear {parent.full_name},

Welcome to Excellence Academy! Your child/children have been successfully enrolled.

Your Children: {student_names}

PARENT PORTAL LOGIN CREDENTIALS:

Username: {username}
Temporary Password: {password}

Login URL: http://127.0.0.1:8000/auth/

IMPORTANT SECURITY NOTICE:
⚠️ You will be required to change this password on first login.
⚠️ Please keep these credentials secure.

Through the Parent Portal, you can:
✓ View your children's attendance records
✓ Check academic performance and grades
✓ View class timetables and schedules
✓ Communicate with teachers
✓ Track fee payments and financial statements
✓ Receive important school announcements

If you have any questions or need assistance logging in, please contact us at {settings.EMAIL_HOST_USER}

Best regards,
Excellence Academy Administration
    """
    
    try:
        result = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[parent.email],
            fail_silently=False,
        )
        print(f"✅ Parent credentials email sent to {parent.email}. Result: {result}")
        return True
    except Exception as e:
        print(f"❌ Error sending parent credentials email: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def send_application_received_email(application):
    """
    Send confirmation email when application is received
    """
    subject = 'Application Received - Excellence Academy'
    
    message = f"""
Dear {application.parent_full_name},

Thank you for submitting an application to Excellence Academy for {application.first_name} {application.last_name}.

APPLICATION DETAILS:

Application Number: {application.application_number}
Submitted On: {application.submitted_at.strftime('%B %d, %Y at %I:%M %p')}
Applying For: {application.applying_for_class}
Department: {application.get_department_display()}

Your application is currently under review. We will contact you within 5-7 business days regarding the next steps.

You can track your application status by contacting our admissions office or checking back with us using your application number: {application.application_number}

Thank you for choosing Excellence Academy.

Best regards,
Excellence Academy Admissions Team
Email: {settings.EMAIL_HOST_USER}
Phone: (School phone number)
    """
    
    try:
        result = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[application.parent_email],
            fail_silently=False,
        )
        print(f"✅ Application received email sent to {application.parent_email}. Result: {result}")
        return True
    except Exception as e:
        print(f"❌ Error sending application received email: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def send_exam_invitation_email(application):
    """
    Send entrance exam invitation to applicant
    """
    subject = 'Entrance Examination Invitation - Excellence Academy'
    
    message = f"""
Dear {application.parent_full_name},

Congratulations! The application for {application.first_name} {application.last_name} has been approved for the entrance examination stage.

APPLICATION DETAILS:

Application Number: {application.application_number}
Student Name: {application.first_name} {application.last_name}
Applying For: {application.applying_for_class}

Your child has been scheduled for an entrance examination. Please contact our admissions office for the exam date and time.

WHAT TO BRING:
✓ This email (printed or on phone)
✓ Application number: {application.application_number}
✓ Valid ID
✓ Writing materials (pens, pencils, eraser)

EXAM LOCATION: Excellence Academy Main Campus
CONTACT: {settings.EMAIL_HOST_USER}

We look forward to meeting {application.first_name}!

Best regards,
Excellence Academy Admissions Team
    """
    
    try:
        result = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[application.parent_email],
            fail_silently=False,
        )
        print(f"✅ Exam invitation email sent to {application.parent_email}. Result: {result}")
        return True
    except Exception as e:
        print(f"❌ Error sending exam invitation email: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def send_application_rejection_email(application, reason=''):
    """
    Send rejection email to applicant
    """
    subject = 'Application Status Update - Excellence Academy'
    
    message = f"""
Dear {application.parent_full_name},

Thank you for your interest in Excellence Academy.

APPLICATION DETAILS:

Application Number: {application.application_number}
Applicant: {application.first_name} {application.last_name}
Applying For: {application.applying_for_class}

After careful consideration, we regret to inform you that we are unable to offer admission at this time.

{f"Reason: {reason}" if reason else "We had a very competitive admissions process this year with many qualified applicants."}

We encourage you to reapply in the future. If you have any questions about this decision or would like feedback, please contact our admissions office.

Thank you for considering Excellence Academy. We wish {application.first_name} all the best in their educational journey.

Best regards,
Excellence Academy Admissions Team
Email: {settings.EMAIL_HOST_USER}
    """
    
    try:
        result = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[application.parent_email],
            fail_silently=False,
        )
        print(f"✅ Rejection email sent to {application.parent_email}. Result: {result}")
        return True
    except Exception as e:
        print(f"❌ Error sending rejection email: {str(e)}")
        import traceback
        traceback.print_exc()
        return False