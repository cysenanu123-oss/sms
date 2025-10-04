# apps/finance/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum, Q
from .models import FeeStructure, StudentFee, Payment
from apps.admissions.models import Student, Parent


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_student_fees(request):
    """
    Get fee information for logged-in student or parent
    """
    user = request.user
    
    if user.role == 'student':
        try:
            student = Student.objects.get(user=user)
            students = [student]
        except Student.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Student profile not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    elif user.role == 'parent':
        try:
            parent = Parent.objects.get(user=user)
            students = parent.children.all()
        except Parent.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Parent profile not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    else:
        return Response({
            'success': False,
            'error': 'Access denied'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get fee data for all students
    fee_data = []
    
    for student in students:
        student_fees = StudentFee.objects.filter(student=student).select_related('fee_structure')
        
        fees_list = []
        for fee in student_fees:
            fees_list.append({
                'id': fee.id,
                'fee_structure': str(fee.fee_structure),
                'term': fee.fee_structure.get_term_display(),
                'total_amount': float(fee.total_amount),
                'discount': float(fee.discount_amount),
                'amount_paid': float(fee.amount_paid),
                'balance': float(fee.balance),
                'status': fee.status,
                'due_date': fee.due_date.isoformat(),
                'is_overdue': fee.is_overdue,
            })
        
        total_pending = sum([f['balance'] for f in fees_list])
        
        fee_data.append({
            'student_id': student.student_id,
            'student_name': f"{student.first_name} {student.last_name}",
            'fees': fees_list,
            'total_pending': total_pending,
        })
    
    return Response({
        'success': True,
        'data': fee_data
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def manage_fee_structures(request):
    """
    Admin endpoint to manage fee structures
    """
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        fee_structures = FeeStructure.objects.all().select_related('class_level')
        
        data = []
        for fs in fee_structures:
            data.append({
                'id': fs.id,
                'class': fs.class_level.name,
                'academic_year': fs.academic_year,
                'term': fs.get_term_display(),
                'total_fee': float(fs.total_fee),
                'due_date': fs.due_date.isoformat(),
                'is_active': fs.is_active,
            })
        
        return Response({
            'success': True,
            'data': data
        })
    
    elif request.method == 'POST':
        # Create new fee structure
        from .serializers import FeeStructureSerializer
        serializer = FeeStructureSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response({
                'success': True,
                'message': 'Fee structure created successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)