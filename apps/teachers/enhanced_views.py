# apps/teachers/enhanced_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import datetime, timedelta
import csv
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from apps.accounts.models import User
from apps.academics.models import Class, Subject, ClassSubject
from apps.admissions.models import Student
from apps.attendance.models import Attendance, AttendanceRecord
from apps.grades.models import Assignment, AssignmentSubmission, Exam, ExamResult


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_assignment(request):
    """
    Create a new assignment for a class
    """
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        title = request.data.get('title')
        description = request.data.get('description')
        class_id = request.data.get('class_id')
        subject_id = request.data.get('subject_id')
        due_date = request.data.get('due_date')
        total_marks = request.data.get('total_marks', 100)
        instructions = request.data.get('instructions', '')
        
        if not all([title, description, class_id, due_date]):
            return Response({
                'success': False,
                'error': 'Missing required fields'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        class_obj = Class.objects.get(id=class_id)
        subject_obj = Subject.objects.get(id=subject_id) if subject_id else None
        
        # Handle file attachment if provided
        attachment = request.FILES.get('attachment')
        
        assignment = Assignment.objects.create(
            title=title,
            description=description,
            class_obj=class_obj,
            subject=subject_obj,
            teacher=user,
            due_date=due_date,
            total_marks=total_marks,
            instructions=instructions,
            attachment=attachment
        )
        
        return Response({
            'success': True,
            'message': 'Assignment created successfully',
            'data': {
                'id': assignment.id,
                'title': assignment.title,
                'due_date': assignment.due_date.isoformat()
            }
        }, status=status.HTTP_201_CREATED)
        
    except Class.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Class not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Error creating assignment: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_attendance_report(request):
    """
    Download attendance report for a class
    Supports CSV and PDF formats
    """
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        class_id = request.GET.get('class_id')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        format_type = request.GET.get('format', 'csv')  # csv or pdf
        
        if not all([class_id, start_date, end_date]):
            return Response({
                'success': False,
                'error': 'Missing required parameters'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        class_obj = Class.objects.get(id=class_id)
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Get all students in the class
        students = Student.objects.filter(
            current_class=class_obj,
            status='active'
        ).order_by('roll_number')
        
        # Get attendance records for the date range
        attendances = Attendance.objects.filter(
            class_obj=class_obj,
            date__gte=start,
            date__lte=end
        ).order_by('date')
        
        if format_type == 'csv':
            return generate_csv_attendance_report(class_obj, students, attendances, start, end)
        else:
            return generate_pdf_attendance_report(class_obj, students, attendances, start, end)
            
    except Class.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Class not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Error generating report: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def generate_csv_attendance_report(class_obj, students, attendances, start_date, end_date):
    """Generate CSV attendance report"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_report_{class_obj.name}_{start_date}_{end_date}.csv"'
    
    writer = csv.writer(response)
    
    # Header
    writer.writerow(['Attendance Report'])
    writer.writerow([f'Class: {class_obj.name}'])
    writer.writerow([f'Period: {start_date} to {end_date}'])
    writer.writerow([])
    
    # Get unique dates
    dates = attendances.values_list('date', flat=True).distinct().order_by('date')
    
    # Column headers
    headers = ['Roll No', 'Student Name'] + [date.strftime('%Y-%m-%d') for date in dates] + ['Present', 'Absent', 'Late', 'Attendance %']
    writer.writerow(headers)
    
    # Student rows
    for student in students:
        row = [student.roll_number or 'N/A', f"{student.first_name} {student.last_name}"]
        
        present_count = 0
        absent_count = 0
        late_count = 0
        
        for date in dates:
            attendance = attendances.filter(date=date).first()
            if attendance:
                record = AttendanceRecord.objects.filter(
                    attendance=attendance,
                    student=student
                ).first()
                
                if record:
                    row.append(record.status.upper()[0])  # P, A, L
                    if record.status == 'present':
                        present_count += 1
                    elif record.status == 'absent':
                        absent_count += 1
                    elif record.status == 'late':
                        late_count += 1
                else:
                    row.append('-')
            else:
                row.append('-')
        
        total_days = len(dates)
        attendance_percentage = (present_count / total_days * 100) if total_days > 0 else 0
        
        row.extend([present_count, absent_count, late_count, f"{attendance_percentage:.1f}%"])
        writer.writerow(row)
    
    return response


def generate_pdf_attendance_report(class_obj, students, attendances, start_date, end_date):
    """Generate PDF attendance report"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title = Paragraph(f"<b>Attendance Report - {class_obj.name}</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    # Period
    period = Paragraph(f"Period: {start_date} to {end_date}", styles['Normal'])
    elements.append(period)
    elements.append(Spacer(1, 20))
    
    # Summary statistics
    total_students = students.count()
    dates = attendances.values_list('date', flat=True).distinct()
    total_days = len(dates)
    
    summary_data = [
        ['Total Students', str(total_students)],
        ['Total Days', str(total_days)],
        ['Report Generated', timezone.now().strftime('%Y-%m-%d %H:%M')]
    ]
    
    summary_table = Table(summary_data, colWidths=[150, 150])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))
    
    # Student attendance table
    table_data = [['Roll No', 'Student Name', 'Present', 'Absent', 'Late', 'Attendance %']]
    
    for student in students:
        present = AttendanceRecord.objects.filter(
            attendance__in=attendances,
            student=student,
            status='present'
        ).count()
        
        absent = AttendanceRecord.objects.filter(
            attendance__in=attendances,
            student=student,
            status='absent'
        ).count()
        
        late = AttendanceRecord.objects.filter(
            attendance__in=attendances,
            student=student,
            status='late'
        ).count()
        
        percentage = (present / total_days * 100) if total_days > 0 else 0
        
        table_data.append([
            student.roll_number or 'N/A',
            f"{student.first_name} {student.last_name}",
            str(present),
            str(absent),
            str(late),
            f"{percentage:.1f}%"
        ])
    
    attendance_table = Table(table_data, colWidths=[60, 150, 50, 50, 50, 80])
    attendance_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(attendance_table)
    
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="attendance_report_{class_obj.name}_{start_date}_{end_date}.pdf"'
    
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_performance_report(request):
    """
    Download class performance report
    """
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        class_id = request.GET.get('class_id')
        report_type = request.GET.get('report_type', 'midterm')  # midterm, final, term
        format_type = request.GET.get('format', 'pdf')
        
        if not class_id:
            return Response({
                'success': False,
                'error': 'Class ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        class_obj = Class.objects.get(id=class_id)
        students = Student.objects.filter(
            current_class=class_obj,
            status='active'
        ).order_by('roll_number')
        
        # Get exam results based on report type
        exams = Exam.objects.filter(
            class_obj=class_obj,
            exam_type=report_type
        )
        
        if format_type == 'csv':
            return generate_csv_performance_report(class_obj, students, exams, report_type)
        else:
            return generate_pdf_performance_report(class_obj, students, exams, report_type)
            
    except Class.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Class not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Error generating report: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def generate_csv_performance_report(class_obj, students, exams, report_type):
    """Generate CSV performance report"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="performance_report_{class_obj.name}_{report_type}.csv"'
    
    writer = csv.writer(response)
    
    # Header
    writer.writerow(['Performance Report'])
    writer.writerow([f'Class: {class_obj.name}'])
    writer.writerow([f'Report Type: {report_type.title()}'])
    writer.writerow([])
    
    # Get subjects from exams
    subjects = exams.values_list('subject__name', flat=True).distinct()
    
    # Column headers
    headers = ['Roll No', 'Student Name'] + list(subjects) + ['Average', 'Grade', 'Rank']
    writer.writerow(headers)
    
    # Calculate student performance
    student_data = []
    
    for student in students:
        row = [student.roll_number or 'N/A', f"{student.first_name} {student.last_name}"]
        
        subject_scores = []
        for subject in subjects:
            exam = exams.filter(subject__name=subject).first()
            if exam:
                result = ExamResult.objects.filter(exam=exam, student=student).first()
                if result:
                    percentage = result.percentage
                    row.append(f"{percentage:.1f}%")
                    subject_scores.append(percentage)
                else:
                    row.append('-')
            else:
                row.append('-')
        
        # Calculate average
        average = sum(subject_scores) / len(subject_scores) if subject_scores else 0
        
        # Determine grade
        if average >= 90:
            grade = 'A+'
        elif average >= 80:
            grade = 'A'
        elif average >= 70:
            grade = 'B+'
        elif average >= 60:
            grade = 'B'
        elif average >= 50:
            grade = 'C+'
        elif average >= 40:
            grade = 'C'
        elif average >= 33:
            grade = 'D'
        else:
            grade = 'F'
        
        row.extend([f"{average:.1f}%", grade, ''])  # Rank will be calculated
        student_data.append((average, row))
    
    # Sort by average and assign ranks
    student_data.sort(key=lambda x: x[0], reverse=True)
    
    for rank, (avg, row) in enumerate(student_data, 1):
        row[-1] = rank
        writer.writerow(row)
    
    return response


def generate_pdf_performance_report(class_obj, students, exams, report_type):
    """Generate PDF performance report"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title = Paragraph(f"<b>Performance Report - {class_obj.name}</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    # Report type
    report_info = Paragraph(f"Report Type: {report_type.title()}", styles['Normal'])
    elements.append(report_info)
    elements.append(Spacer(1, 20))
    
    # Get subjects
    subjects = exams.values_list('subject__name', flat=True).distinct()
    
    # Build table data
    table_data = [['Roll No', 'Student Name'] + list(subjects) + ['Avg', 'Grade']]
    
    for student in students:
        row = [student.roll_number or 'N/A', f"{student.first_name} {student.last_name}"[:20]]
        
        subject_scores = []
        for subject in subjects:
            exam = exams.filter(subject__name=subject).first()
            if exam:
                result = ExamResult.objects.filter(exam=exam, student=student).first()
                if result:
                    percentage = result.percentage
                    row.append(f"{percentage:.0f}%")
                    subject_scores.append(percentage)
                else:
                    row.append('-')
            else:
                row.append('-')
        
        average = sum(subject_scores) / len(subject_scores) if subject_scores else 0
        
        if average >= 90:
            grade = 'A+'
        elif average >= 80:
            grade = 'A'
        elif average >= 70:
            grade = 'B+'
        elif average >= 60:
            grade = 'B'
        elif average >= 50:
            grade = 'C+'
        elif average >= 40:
            grade = 'C'
        elif average >= 33:
            grade = 'D'
        else:
            grade = 'F'
        
        row.extend([f"{average:.0f}%", grade])
        table_data.append(row)
    
    # Create table
    performance_table = Table(table_data)
    performance_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
    ]))
    
    elements.append(performance_table)
    
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="performance_report_{class_obj.name}_{report_type}.pdf"'
    
    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_resource(request):
    """
    Upload teaching resources (PDFs, videos, links)
    """
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        title = request.data.get('title')
        description = request.data.get('description', '')
        class_id = request.data.get('class_id')
        subject_id = request.data.get('subject_id')
        resource_type = request.data.get('resource_type')  # pdf, video, link
        
        if not all([title, class_id, resource_type]):
            return Response({
                'success': False,
                'error': 'Missing required fields'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        class_obj = Class.objects.get(id=class_id)
        subject_obj = Subject.objects.get(id=subject_id) if subject_id else None
        
        # Handle different resource types
        file_upload = None
        external_link = None
        
        if resource_type in ['pdf', 'video']:
            file_upload = request.FILES.get('file')
            if not file_upload:
                return Response({
                    'success': False,
                    'error': 'File is required for this resource type'
                }, status=status.HTTP_400_BAD_REQUEST)
        elif resource_type == 'link':
            external_link = request.data.get('link')
            if not external_link:
                return Response({
                    'success': False,
                    'error': 'Link is required for this resource type'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create resource (you'll need to create this model)
        from apps.academics.models import TeachingResource
        
        resource = TeachingResource.objects.create(
            title=title,
            description=description,
            class_obj=class_obj,
            subject=subject_obj,
            teacher=user,
            resource_type=resource_type,
            file=file_upload,
            external_link=external_link
        )
        
        return Response({
            'success': True,
            'message': 'Resource uploaded successfully',
            'data': {
                'id': resource.id,
                'title': resource.title,
                'resource_type': resource.resource_type
            }
        }, status=status.HTTP_201_CREATED)
        
    except Class.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Class not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Error uploading resource: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_teacher_resources(request):
    """Get all resources uploaded by teacher"""
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from apps.academics.models import TeachingResource
        
        resources = TeachingResource.objects.filter(
            teacher=user
        ).select_related('class_obj', 'subject').order_by('-created_at')
        
        resources_data = []
        for resource in resources:
            resources_data.append({
                'id': resource.id,
                'title': resource.title,
                'description': resource.description,
                'class': resource.class_obj.name,
                'subject': resource.subject.name if resource.subject else 'General',
                'resource_type': resource.resource_type,
                'file_url': resource.file.url if resource.file else None,
                'external_link': resource.external_link,
                'created_at': resource.created_at.isoformat()
            })
        
        return Response({
            'success': True,
            'data': resources_data
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Error fetching resources: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)