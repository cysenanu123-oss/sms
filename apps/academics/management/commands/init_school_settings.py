# apps/academics/management/commands/init_school_settings.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.academics.models import SchoolSettings


class Command(BaseCommand):
    help = 'Initialize school settings with default values'

    def handle(self, *args, **kwargs):
        if SchoolSettings.objects.exists():
            self.stdout.write(self.style.WARNING('School settings already exist. Skipping initialization.'))
            return

        today = timezone.now().date()
        
        # Create default school settings
        settings = SchoolSettings.objects.create(
            school_name="Unique Success Academy",
            school_motto="Excellence in Education",
            school_address="Accra, Ghana",
            school_phone="+233 XX XXX XXXX",
            school_email="info@uniquesuccessacademy.edu.gh",
            school_website="https://uniquesuccessacademy.edu.gh",
            
            # Academic year settings
            current_academic_year="2024/2025",
            academic_year_start=today.replace(month=9, day=1),  # September 1st
            academic_year_end=today.replace(year=today.year + 1, month=7, day=31),  # July 31st next year
            
            # Current term - First Term
            current_term="first",
            term_start_date=today.replace(month=9, day=1),  # September 1st
            term_end_date=today.replace(month=12, day=15),  # December 15th
            
            # Grading system
            grading_system="percentage",
            
            # Fees
            admission_fee=500.00,
            application_fee=50.00,
            
            # Entrance exam settings
            entrance_exam_required=True,
            exam_duration_minutes=120,
            exam_pass_percentage=50
        )

        self.stdout.write(self.style.SUCCESS(f'Successfully created school settings for {settings.school_name}'))
        self.stdout.write(self.style.SUCCESS(f'Current Term: {settings.get_current_term_display()}'))
        self.stdout.write(self.style.SUCCESS(f'Academic Year: {settings.current_academic_year}'))
