from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import FeeStructure, StudentFee
from apps.admissions.models import Student


@receiver(post_save, sender=FeeStructure)
def create_or_update_student_fees(sender, instance, created, **kwargs):
    """
    Automatically create OR UPDATE StudentFee records
    """
    if instance.is_active:
        students = Student.objects.filter(
            current_class=instance.class_level,
            status='active'
        )
        
        if created:
            print(f"📋 Creating fees for {students.count()} students in {instance.class_level.name}")
        else:
            print(f"🔄 Updating fees for {students.count()} students in {instance.class_level.name}")
        
        student_fees_created = 0
        student_fees_updated = 0
        
        for student in students:
            existing_fee = StudentFee.objects.filter(
                student=student,
                fee_structure=instance
            ).first()
            
            if not existing_fee:
                StudentFee.objects.create(
                    student=student,
                    fee_structure=instance,
                    total_amount=instance.total_fee,
                    due_date=instance.due_date,
                    status='pending'
                )
                student_fees_created += 1
            else:
                old_total = existing_fee.total_amount
                new_total = instance.total_fee
                
                if old_total != new_total:
                    existing_fee.total_amount = new_total
                    existing_fee.due_date = instance.due_date
                    existing_fee.update_status()
                    existing_fee.save()
                    
                    student_fees_updated += 1
                    print(f"  ✓ Updated {student.student_id}: GHS {old_total} → GHS {new_total}")
        
        if created:
            print(f"✅ Created {student_fees_created} StudentFee records")
        else:
            print(f"✅ Updated {student_fees_updated} StudentFee records")


@receiver(post_save, sender=Student)
def create_fees_for_new_student(sender, instance, created, **kwargs):
    """
    When a new student is enrolled, create StudentFee records
    """
    if created and instance.current_class and instance.status == 'active':
        fee_structures = FeeStructure.objects.filter(
            class_level=instance.current_class,
            is_active=True
        )
        
        print(f"📋 Creating fees for new student: {instance.student_id}")
        
        for fee_structure in fee_structures:
            existing_fee = StudentFee.objects.filter(
                student=instance,
                fee_structure=fee_structure
            ).exists()
            
            if not existing_fee:
                StudentFee.objects.create(
                    student=instance,
                    fee_structure=fee_structure,
                    total_amount=fee_structure.total_fee,
                    due_date=fee_structure.due_date,
                    status='pending'
                )
                print(f"✅ Created fee record: {fee_structure}")
