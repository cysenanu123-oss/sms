# apps/academics/management/commands/add_subjects.py
# Create this file structure:
# apps/academics/management/__init__.py (empty file)
# apps/academics/management/commands/__init__.py (empty file)
# apps/academics/management/commands/add_subjects.py (this file)

from django.core.management.base import BaseCommand
from apps.academics.models import Subject


class Command(BaseCommand):
    help = 'Add Ghana curriculum subjects (KG, Primary, JHS)'

    def handle(self, *args, **kwargs):
        subjects_data = [
            # KINDERGARTEN (KG) SUBJECTS
            {'name': 'Numeracy', 'code': 'KG-NUM', 'description': 'Basic mathematics concepts for kindergarten'},
            {'name': 'Literacy', 'code': 'KG-LIT', 'description': 'Language and communication skills'},
            {'name': 'Creative Arts', 'code': 'KG-CA', 'description': 'Creative and artistic expression'},
            {'name': 'Our World Our People', 'code': 'KG-OWOP', 'description': 'Understanding environment and community'},
            {'name': 'Physical Education', 'code': 'KG-PE', 'description': 'Motor skills and health'},
            {'name': 'Ghanaian Language', 'code': 'KG-GHL', 'description': 'Local language instruction'},
            
            # PRIMARY SCHOOL SUBJECTS (Basic 1-6)
            {'name': 'English Language', 'code': 'PRI-ENG', 'description': 'English language instruction'},
            {'name': 'Mathematics', 'code': 'PRI-MATH', 'description': 'Mathematics for primary level'},
            {'name': 'Science', 'code': 'PRI-SCI', 'description': 'Basic and integrated science'},
            {'name': 'Ghanaian Language', 'code': 'PRI-GHL', 'description': 'Ghanaian language and culture'},
            {'name': 'History', 'code': 'PRI-HIST', 'description': 'History education'},
            {'name': 'Social Studies', 'code': 'PRI-SS', 'description': 'Social studies and civic education'},
            {'name': 'Creative Arts', 'code': 'PRI-CA', 'description': 'Creative arts and design'},
            {'name': 'Computing', 'code': 'PRI-ICT', 'description': 'ICT and computing skills'},
            {'name': 'Religious and Moral Education', 'code': 'PRI-RME', 'description': 'Religious and moral instruction'},
            {'name': 'Physical Education', 'code': 'PRI-PE', 'description': 'Physical education and sports'},
            {'name': 'French', 'code': 'PRI-FRE', 'description': 'French language (optional)'},
            
            # JUNIOR HIGH SCHOOL (JHS) SUBJECTS (Basic 7-10)
            {'name': 'English Language', 'code': 'JHS-ENG', 'description': 'English language for JHS'},
            {'name': 'Mathematics', 'code': 'JHS-MATH', 'description': 'Mathematics for JHS'},
            {'name': 'Integrated Science', 'code': 'JHS-SCI', 'description': 'Integrated science'},
            {'name': 'Social Studies', 'code': 'JHS-SS', 'description': 'Social studies'},
            {'name': 'Ghanaian Language', 'code': 'JHS-GHL', 'description': 'Ghanaian language studies'},
            {'name': 'French', 'code': 'JHS-FRE', 'description': 'French language'},
            {'name': 'Creative Arts and Design', 'code': 'JHS-CAD', 'description': 'Creative arts and design'},
            {'name': 'Computing', 'code': 'JHS-ICT', 'description': 'Computing and ICT'},
            {'name': 'Career Technology', 'code': 'JHS-CT', 'description': 'Career technology and design'},
            {'name': 'Religious and Moral Education', 'code': 'JHS-RME', 'description': 'Religious and moral education'},
            {'name': 'Physical and Health Education', 'code': 'JHS-PHE', 'description': 'Physical and health education'},
            {'name': 'Basic Design and Technology', 'code': 'JHS-BDT', 'description': 'Basic design and technology'},
        ]

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for subject_data in subjects_data:
            subject, created = Subject.objects.update_or_create(
                code=subject_data['code'],
                defaults={
                    'name': subject_data['name'],
                    'description': subject_data['description']
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created: {subject.name} ({subject.code})')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'→ Updated: {subject.name} ({subject.code})')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Done! Created: {created_count}, Updated: {updated_count}'
            )
        )