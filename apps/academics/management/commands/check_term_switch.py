# apps/academics/management/commands/check_term_switch.py
"""
Management command to automatically switch terms based on dates.
Run this as a cron job daily: python manage.py check_term_switch
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.academics.models import SchoolSettings


class Command(BaseCommand):
    help = 'Check if term needs to be switched based on current date'

    def handle(self, *args, **kwargs):
        settings = SchoolSettings.objects.first()

        if not settings:
            self.stdout.write(self.style.ERROR('❌ School settings not found'))
            return

        today = timezone.now().date()

        # Check if we're past the current term's end date
        if settings.term_end_date and today > settings.term_end_date:
            old_term = settings.get_current_term_display()
            old_year = settings.current_academic_year

            # Determine next term
            if settings.current_term == 'first':
                settings.current_term = 'second'
                # Second term typically starts in January
                settings.term_start_date = today.replace(month=1, day=6)
                settings.term_end_date = today.replace(month=4, day=15)

            elif settings.current_term == 'second':
                settings.current_term = 'third'
                # Third term typically starts in May
                settings.term_start_date = today.replace(month=5, day=1)
                settings.term_end_date = today.replace(month=7, day=31)

            elif settings.current_term == 'third':
                # New academic year - move to first term
                settings.current_term = 'first'

                # Update academic year (e.g., 2024/2025 -> 2025/2026)
                current_years = settings.current_academic_year.split('/')
                if len(current_years) == 2:
                    next_year_start = int(current_years[0]) + 1
                    next_year_end = int(current_years[1]) + 1
                    settings.current_academic_year = f"{next_year_start}/{next_year_end}"

                # First term starts in September
                next_year = today.year + 1
                settings.term_start_date = today.replace(year=next_year, month=9, day=1)
                settings.term_end_date = today.replace(year=next_year, month=12, day=15)

            settings.save()

            new_term = settings.get_current_term_display()
            new_year = settings.current_academic_year

            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Term switched successfully!\n'
                    f'   Old: {old_term} ({old_year})\n'
                    f'   New: {new_term} ({new_year})\n'
                    f'   Start: {settings.term_start_date}\n'
                    f'   End: {settings.term_end_date}'
                )
            )

            # Create fee structures for new term (optional)
            self.create_fee_structures_for_new_term(settings)

        else:
            days_remaining = (settings.term_end_date - today).days if settings.term_end_date else 0
            self.stdout.write(
                self.style.WARNING(
                    f'⏳ Current term: {settings.get_current_term_display()} '
                    f'({settings.current_academic_year})\n'
                    f'   Days remaining: {days_remaining}'
                )
            )

    def create_fee_structures_for_new_term(self, settings):
        """
        Automatically create fee structures for the new term
        based on the previous term's fee structures
        """
        from apps.finance.models import FeeStructure
        from apps.academics.models import Class

        # Get previous term
        term_order = {'first': 0, 'second': 1, 'third': 2}
        current_term_index = term_order.get(settings.current_term, 0)

        if current_term_index == 0:  # If first term, get from previous year third term
            previous_term = 'third'
            # Get previous year
            years = settings.current_academic_year.split('/')
            prev_year = f"{int(years[0])-1}/{int(years[1])-1}"
        else:
            # Get previous term in same year
            previous_term = list(term_order.keys())[current_term_index - 1]
            prev_year = settings.current_academic_year

        # Copy fee structures from previous term
        previous_fees = FeeStructure.objects.filter(
            academic_year=prev_year,
            term=previous_term,
            is_active=True
        )

        created_count = 0
        for prev_fee in previous_fees:
            # Check if fee structure already exists for new term
            exists = FeeStructure.objects.filter(
                class_level=prev_fee.class_level,
                academic_year=settings.current_academic_year,
                term=settings.current_term
            ).exists()

            if not exists:
                # Create new fee structure based on previous term
                FeeStructure.objects.create(
                    class_level=prev_fee.class_level,
                    academic_year=settings.current_academic_year,
                    term=settings.current_term,
                    tuition_fee=prev_fee.tuition_fee,
                    admission_fee=0,  # No admission fee for continuing students
                    examination_fee=prev_fee.examination_fee,
                    library_fee=prev_fee.library_fee,
                    sports_fee=prev_fee.sports_fee,
                    laboratory_fee=prev_fee.laboratory_fee,
                    uniform_fee=prev_fee.uniform_fee,
                    transport_fee=prev_fee.transport_fee,
                    miscellaneous_fee=prev_fee.miscellaneous_fee,
                    due_date=settings.term_end_date,
                    is_active=True,
                    created_by=None
                )
                created_count += 1

        if created_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Created {created_count} fee structures for new term'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    '⚠️  No new fee structures created (already exist or no previous data)'
                )
            )
