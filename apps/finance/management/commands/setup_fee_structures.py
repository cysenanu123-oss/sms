# apps/finance/management/commands/setup_fee_structures.py
"""
Create fee structures for all classes for all terms.
Usage: python manage.py setup_fee_structures
"""
from django.core.management.base import BaseCommand
from apps.academics.models import Class, SchoolSettings
from apps.finance.models import FeeStructure
from datetime import datetime


class Command(BaseCommand):
    help = 'Create fee structures for all classes for all three terms'

    def add_arguments(self, parser):
        parser.add_argument(
            '--academic-year',
            type=str,
            default=None,
            help='Academic year (e.g., 2024/2025). Defaults to current year from settings.'
        )

    def handle(self, *args, **kwargs):
        academic_year = kwargs.get('academic_year')

        if not academic_year:
            settings = SchoolSettings.objects.first()
            if settings:
                academic_year = settings.current_academic_year
            else:
                academic_year = '2024/2025'

        self.stdout.write(f'\n🎓 Setting up fee structures for {academic_year}...\n')

        # Default fee amounts for each grade level (in GHS)
        DEFAULT_FEES = {
            'nursery': {
                'tuition_fee': 300,
                'examination_fee': 20,
                'library_fee': 10,
                'sports_fee': 15,
                'laboratory_fee': 0,
                'uniform_fee': 0,
                'transport_fee': 0,
                'miscellaneous_fee': 10,
            },
            'kindergarten': {
                'tuition_fee': 350,
                'examination_fee': 25,
                'library_fee': 15,
                'sports_fee': 20,
                'laboratory_fee': 0,
                'uniform_fee': 0,
                'transport_fee': 0,
                'miscellaneous_fee': 15,
            },
            'primary': {  # Class 1-6
                'tuition_fee': 400,
                'examination_fee': 30,
                'library_fee': 20,
                'sports_fee': 25,
                'laboratory_fee': 20,
                'uniform_fee': 0,
                'transport_fee': 0,
                'miscellaneous_fee': 20,
            },
            'jhs': {  # JHS 1-3
                'tuition_fee': 500,
                'examination_fee': 40,
                'library_fee': 30,
                'sports_fee': 30,
                'laboratory_fee': 40,
                'uniform_fee': 0,
                'transport_fee': 0,
                'miscellaneous_fee': 25,
            }
        }

        # Term dates
        TERMS = [
            ('first', '2024-09-01', '2024-12-15'),
            ('second', '2025-01-06', '2025-04-15'),
            ('third', '2025-05-01', '2025-07-31'),
        ]

        classes = Class.objects.all()
        created_count = 0
        skipped_count = 0
        total_expected = len(classes) * 3  # 3 terms per class

        for class_obj in classes:
            # Determine fee category based on class name
            class_name_lower = class_obj.name.lower()

            if 'nursery' in class_name_lower:
                fee_category = 'nursery'
            elif 'kindergarten' in class_name_lower or 'kg' in class_name_lower:
                fee_category = 'kindergarten'
            elif 'jhs' in class_name_lower or 'junior high' in class_name_lower:
                fee_category = 'jhs'
            else:
                fee_category = 'primary'

            fees = DEFAULT_FEES[fee_category]

            # Create fee structure for each term
            for term, start_date, end_date in TERMS:
                # Check if already exists
                exists = FeeStructure.objects.filter(
                    class_level=class_obj,
                    academic_year=academic_year,
                    term=term
                ).exists()

                if exists:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠️  {class_obj.name} - {term.capitalize()} Term: Already exists'
                        )
                    )
                    continue

                # Create fee structure
                # Convert date strings to date objects
                due_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()

                FeeStructure.objects.create(
                    class_level=class_obj,
                    academic_year=academic_year,
                    term=term,
                    admission_fee=0,  # Admission fee only charged once
                    due_date=due_date_obj,
                    late_fee_amount=50,  # GHS 50 late fee
                    late_fee_applicable_after=due_date_obj,
                    is_active=True,
                    **fees
                )

                created_count += 1
                total_fee = sum(fees.values())

                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ {class_obj.name} - {term.capitalize()} Term: '
                        f'GHS {total_fee} (Created)'
                    )
                )

        self.stdout.write('\n' + '='*60)
        self.stdout.write(
            self.style.SUCCESS(
                f'\n📊 Summary:\n'
                f'   Total Classes: {classes.count()}\n'
                f'   Expected Fee Structures: {total_expected}\n'
                f'   Created: {created_count}\n'
                f'   Skipped (Already Exist): {skipped_count}\n'
                f'   Academic Year: {academic_year}\n'
            )
        )

        if created_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    '\n✅ Fee structures created successfully!\n'
                    '   Next step: Assign fees to students using:\n'
                    '   python manage.py assign_student_fees\n'
                )
            )
