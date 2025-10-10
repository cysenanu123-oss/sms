# apps/finance/management/commands/fix_student_fees.py
# CREATE THIS NEW FILE

from django.core.management.base import BaseCommand
from apps.finance.models import StudentFee, Payment
from django.db.models import Sum


class Command(BaseCommand):
    help = 'Fix student fee balances by recalculating from actual payments'

    def handle(self, *args, **options):
        self.stdout.write('🔧 Starting to fix student fees...\n')
        self.stdout.write('='*60)
        
        all_student_fees = StudentFee.objects.all()
        total_fixed = 0
        
        for student_fee in all_student_fees:
            # Get the ACTUAL total paid from completed payments
            actual_paid = Payment.objects.filter(
                student_fee=student_fee,
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            old_amount_paid = student_fee.amount_paid
            old_balance = student_fee.balance
            
            # Update with correct amount
            student_fee.amount_paid = actual_paid
            student_fee.update_status()
            student_fee.save()
            
            new_balance = student_fee.balance
            
            # Only print if there was a difference
            if old_amount_paid != actual_paid:
                self.stdout.write(
                    self.style.WARNING(
                        f'\n📝 {student_fee.student.student_id} - '
                        f'{student_fee.student.first_name} {student_fee.student.last_name}'
                    )
                )
                self.stdout.write(f'   Total Fee: GHS {student_fee.total_amount}')
                self.stdout.write(
                    self.style.ERROR(
                        f'   ❌ OLD Amount Paid: GHS {old_amount_paid} (WRONG)'
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'   ✅ NEW Amount Paid: GHS {actual_paid} (CORRECT)'
                    )
                )
                self.stdout.write(
                    self.style.ERROR(
                        f'   ❌ OLD Balance: GHS {old_balance}'
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'   ✅ NEW Balance: GHS {new_balance}'
                    )
                )
                total_fixed += 1
        
        self.stdout.write('\n' + '='*60)
        if total_fixed > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ FIXED {total_fixed} student fee records!'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    '✅ All student fees were already correct!'
                )
            )
        self.stdout.write('='*60)