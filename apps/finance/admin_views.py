# ============================================
# FILE 2: apps/finance/admin_views.py (NEW FILE)
# ============================================

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum, Q
from .models import StudentFee, Payment, FeeStructure
from apps.admissions.models import Student


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def record_payment(request):
    """
    🔥 FIXED: Record payment without multiplication
    """
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        student_id = request.data.get('student_id')
        amount = float(request.data.get('amount', 0))
        payment_method = request.data.get('payment_method', 'cash')
        reference = request.data.get('reference_number', '')
        notes = request.data.get('notes', '')
        
        # Get student
        student = Student.objects.get(student_id=student_id)
        
        # Get active student fee
        student_fee = StudentFee.objects.filter(
            student=student,
            status__in=['pending', 'partial', 'overdue']
        ).first()
        
        if not student_fee:
            return Response({
                'success': False,
                'error': 'No pending fees found for this student'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Create payment (it will auto-update the student fee)
        payment = Payment.objects.create(
            student_fee=student_fee,
            amount=amount,
            payment_method=payment_method,
            reference_number=reference,
            notes=notes,
            status='completed',
            processed_by=request.user
        )
        
        # Refresh to get updated values
        student_fee.refresh_from_db()
        
        return Response({
            'success': True,
            'message': 'Payment recorded successfully',
            'data': {
                'receipt_number': payment.receipt_number,
                'amount': float(payment.amount),
                'balance': float(student_fee.balance),
                'status': student_fee.status
            }
        }, status=status.HTTP_201_CREATED)
        
    except Student.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Student not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pending_fees(request):
    """Get all students with pending fees"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Auto-fix any discrepancies before showing
    student_fees = StudentFee.objects.filter(
        status__in=['pending', 'partial', 'overdue']
    ).select_related('student', 'fee_structure')
    
    # Force recalculation for all
    for fee in student_fees:
        fee.save()  # This triggers recalculation
    
    # Refresh and get updated data
    student_fees = StudentFee.objects.filter(
        status__in=['pending', 'partial', 'overdue']
    ).select_related('student', 'fee_structure')
    
    data = []
    for fee in student_fees:
        data.append({
            'student_id': fee.student.student_id,
            'student_name': f"{fee.student.first_name} {fee.student.last_name}",
            'class': fee.student.current_class.name if fee.student.current_class else 'N/A',
            'total_amount': float(fee.total_amount),
            'amount_paid': float(fee.amount_paid),
            'balance': float(fee.balance),
            'status': fee.status,
            'due_date': fee.due_date.isoformat()
        })
    
    return Response({
        'success': True,
        'count': len(data),
        'data': data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_finance_overview(request):
    """Get finance overview statistics"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Force recalculation
    for fee in StudentFee.objects.all():
        fee.save()
    
    total_expected = StudentFee.objects.aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    total_collected = StudentFee.objects.aggregate(
        total=Sum('amount_paid')
    )['total'] or 0
    
    total_pending = total_expected - total_collected
    
    pending_count = StudentFee.objects.filter(
        status__in=['pending', 'partial', 'overdue']
    ).count()
    
    return Response({
        'success': True,
        'data': {
            'total_expected': float(total_expected),
            'total_collected': float(total_collected),
            'total_pending': float(total_pending),
            'pending_count': pending_count
        }
    })


