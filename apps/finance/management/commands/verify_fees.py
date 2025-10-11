# ============================================
# FILE 4: apps/finance/management/commands/verify_fees.py (NEW)
# ============================================

from django.core.management.base import BaseCommand
from apps.finance.models import StudentFee
from django.db.models import Sum


class Command(BaseCommand):
    help = 'Verify and auto-fix all student fees'

    def handle(self, *args, **options):
        self.stdout.write('🔍 Verifying all student fees...\n')
        self.stdout.write('='*60)
        
        all_fees = StudentFee.objects.all()
        issues_found = 0
        issues_fixed = 0
        
        for fee in all_fees:
            # Get actual total from payments
            from apps.finance.models import Payment
            actual_paid = Payment.objects.filter(
                student_fee=fee,
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            # Check if there's a discrepancy
            if fee.amount_paid != actual_paid:
                issues_found += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'\n⚠️  {fee.student.student_id} - '
                        f'{fee.student.first_name} {fee.student.last_name}'
                    )
                )
                self.stdout.write(
                    f'   Stored: GHS {fee.amount_paid} | '
                    f'Actual: GHS {actual_paid}'
                )
                
                # Auto-fix by saving (triggers recalculation)
                fee.save()
                issues_fixed += 1
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'   ✅ Fixed! New balance: GHS {fee.balance}'
                    )
                )
        
        self.stdout.write('\n' + '='*60)
        if issues_found == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    '✅ All fees are correct! No issues found.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Fixed {issues_fixed} out of {issues_found} issues'
                )
            )
        self.stdout.write('='*60)