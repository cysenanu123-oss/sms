# apps/parents/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from apps.admissions.models import Parent, Student


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_dashboard_data(request):
    """
    Get parent dashboard with all linked children data
    """
    if request.user.role != 'parent' and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Parent access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        parent = Parent.objects.get(user=request.user)
    except Parent.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Parent profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Get all children linked to this parent
    children = parent.children.all()
    
    children_data = []
    for child in children:
        child_data = {
            'id': child.id,
            'student_id': child.student_id,
            'name': f"{child.first_name} {child.last_name}",
            'class': child.current_class.name if child.current_class else 'Not Assigned',
            'class_id': child.current_class.id if child.current_class else None,
            'academic_year': child.academic_year,
            'status': child.status,
            'admission_date': child.admission_date.isoformat(),
            'attendance_rate': 95.5,  # TODO: Calculate from attendance
            'overall_grade': 'A',      # TODO: Calculate from grades
            'average_percentage': 87.3, # TODO: Calculate
            'pending_fees': 250,        # TODO: Get from finance
            'class_rank': 3,            # TODO: Calculate
            'total_students': 45,       # TODO: Get from class
        }
        children_data.append(child_data)
    
    # Parent info
    parent_info = {
        'full_name': parent.full_name,
        'email': parent.email,
        'phone': parent.phone,
        'relationship': parent.relationship,
        'total_children': len(children_data),
    }
    
    return Response({
        'success': True,
        'data': {
            'parent_info': parent_info,
            'children': children_data,
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_child_details(request, student_id):
    """
    Get detailed information about a specific child
    """
    if request.user.role != 'parent' and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Parent access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        parent = Parent.objects.get(user=request.user)
        child = Student.objects.get(id=student_id)
        
        # Verify this child belongs to this parent
        if child not in parent.children.all():
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get detailed child data including courses, timetable, etc.
        from apps.students.views import get_student_timetable_helper
        from apps.academics.models import ClassSubject
        
        current_class = child.current_class
        
        # Get courses
        class_subjects = ClassSubject.objects.filter(class_obj=current_class).select_related('subject', 'teacher')
        courses = []
        for cs in class_subjects:
            courses.append({
                'subject': cs.subject.name,
                'teacher': cs.teacher.get_full_name() if cs.teacher else 'TBA',
            })
        
        # Get timetable
        timetable_data = get_student_timetable_helper(current_class)
        
        child_data = {
            'student_id': child.student_id,
            'name': f"{child.first_name} {child.last_name}",
            'class': current_class.name if current_class else 'Not Assigned',
            'roll_number': child.roll_number,
            'courses': courses,
            'timetable': timetable_data,
        }
        
        return Response({
            'success': True,
            'data': child_data
        })
        
    except Parent.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Parent profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Student.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Student not found'
        }, status=status.HTTP_404_NOT_FOUND)