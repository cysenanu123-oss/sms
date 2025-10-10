# apps/finance/management/commands/create_student_fees.py
from django.core.management.base import BaseCommand
from apps.finance.models import FeeStructure, StudentFee
from apps.admissions.models import Student


class Command(BaseCommand):
    help = 'Create StudentFee records for all existing FeeStructures and Students'

    def add_arguments(self, parser):
        parser.add_argument(
            '--class-id',
            type=int,
            help='Create fees for specific class only',
        )
        parser.add_argument(
            '--fee-structure-id',
            type=int,
            help='Create fees for specific fee structure only',
        )

    def handle(self, *args, **options):
        class_id = options.get('class_id')
        fee_structure_id = options.get('fee_structure_id')
        
        # Get fee structures
        fee_structures = FeeStructure.objects.filter(is_active=True)
        
        if fee_structure_id:
            fee_structures = fee_structures.filter(id=fee_structure_id)
        
        if class_id:
            fee_structures = fee_structures.filter(class_level_id=class_id)
        
        if not fee_structures.exists():
            self.stdout.write(self.style.WARNING('No fee structures found'))
            return
        
        total_created = 0
        total_existing = 0
        
        for fee_structure in fee_structures:
            self.stdout.write(
                self.style.NOTICE(
                    f'\nProcessing: {fee_structure.class_level.name} - '
                    f'{fee_structure.academic_year} - {fee_structure.get_term_display()}'
                )
            )
            
            # Get all active students in this class
            students = Student.objects.filter(
                current_class=fee_structure.class_level,
                status='active'
            )
            
            self.stdout.write(f'  Found {students.count()} active students')
            
            created_count = 0
            for student in students:
                # Check if fee already exists
                existing_fee = StudentFee.objects.filter(
                    student=student,
                    fee_structure=fee_structure
                ).exists()
                
                if not existing_fee:
                    StudentFee.objects.create(
                        student=student,
                        fee_structure=fee_structure,
                        total_amount=fee_structure.total_fee,
                        due_date=fee_structure.due_date,
                        status='pending'
                    )
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'    ✓ Created fee for {student.student_id} - '
                            f'{student.first_name} {student.last_name}'
                        )
                    )
                else:
                    total_existing += 1
            
            total_created += created_count
            
            if created_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  Created {created_count} new StudentFee records'
                    )
                )
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(
            self.style.SUCCESS(
                f'✓ SUMMARY: Created {total_created} new StudentFee records'
            )
        )
        if total_existing > 0:
            self.stdout.write(
                self.style.NOTICE(
                    f'  {total_existing} StudentFee records already existed'
                )
            )
        self.stdout.write('='*60)
