from django.core.management.base import BaseCommand
from django.utils import timezone
from subscriptions.models import Subscription
from billing.services import generate_invoice

class Command(BaseCommand):
    help = 'Finds active subscriptions due today or earlier and generates invoices idempotently.'

    def handle(self, *args, **options):
        today = timezone.now().date()
        self.stdout.write(f"Running invoice generation for active subscriptions due on or before {today}...")

        active_subs = Subscription.objects.filter(
            status=Subscription.STATUS_ACTIVE
        ).select_related('customer', 'plan').prefetch_related('lines')

        generated_count = 0
        skipped_count = 0
        closed_count = 0

        for sub in active_subs:
            # Check auto-close rule first
            if sub.check_and_auto_close():
                closed_count += 1
                self.stdout.write(f"Auto-closed subscription {sub.number} (plan expired).")
                continue

            if not sub.lines.exists():
                self.stdout.write(self.style.WARNING(f"Skipping {sub.number}: No subscription lines configured."))
                skipped_count += 1
                continue

            sub_inv_count = 0
            while True:
                due_date = sub.next_billing_date or sub.start_date
                if not due_date or due_date > today:
                    break

                prev_billing_date = sub.next_billing_date
                inv = generate_invoice(sub)
                if inv:
                    sub_inv_count += 1
                    generated_count += 1
                    self.stdout.write(self.style.SUCCESS(f"Generated/Verified {inv.number} for {sub.number} (Period: {inv.period_start} to {inv.period_end})"))

                if sub.check_and_auto_close():
                    closed_count += 1
                    self.stdout.write(f"Auto-closed subscription {sub.number} (plan expired).")
                    break

                if sub.next_billing_date == prev_billing_date:
                    break

            if sub_inv_count == 0:
                skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Generated/Verified: {generated_count}, Skipped: {skipped_count}, Auto-closed: {closed_count}."
            )
        )
