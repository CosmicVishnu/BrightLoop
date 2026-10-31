from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
import datetime
from catalog.models import Plan
from subscriptions.models import Subscription
from billing.models import Invoice, Payment

User = get_user_model()

class DashboardTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser('admin_dash@test.com', 'Admin@1234')
        self.staff = User.objects.create_user('staff_dash@test.com', 'Staff@1234', role=User.ROLE_STAFF)
        self.customer = User.objects.create_user('cust_dash@test.com', 'Customer@1234', role=User.ROLE_CUSTOMER)

        self.plan = Plan.objects.create(name='Pro Plan', price=Decimal('200.00'))
        self.sub = Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            status=Subscription.STATUS_ACTIVE
        )

    def test_dashboard_access_by_role(self):
        # Customer forbidden
        self.client.force_login(self.customer)
        res = self.client.get('/dashboard/')
        self.assertEqual(res.status_code, 403)

        # Staff allowed
        self.client.force_login(self.staff)
        res = self.client.get('/dashboard/')
        self.assertEqual(res.status_code, 200)

        # Admin allowed
        self.client.force_login(self.admin)
        res = self.client.get('/dashboard/')
        self.assertEqual(res.status_code, 200)

    def test_dashboard_metrics(self):
        today = timezone.now().date()
        # Create an overdue invoice
        inv = Invoice.objects.create(
            subscription=self.sub,
            customer=self.customer,
            period_start=today - datetime.timedelta(days=30),
            period_end=today,
            due_date=today - datetime.timedelta(days=10),
            status=Invoice.STATUS_CONFIRMED,
            subtotal=Decimal('500.00'),
            total=Decimal('500.00')
        )
        Payment.objects.create(
            invoice=inv,
            method='card',
            amount=Decimal('200.00'),
            date=today - datetime.timedelta(days=5)
        )

        self.client.force_login(self.admin)
        res = self.client.get('/dashboard/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['active_subscriptions_count'], 1)
        self.assertEqual(res.context['total_revenue_collected'], Decimal('200.00'))
        self.assertEqual(res.context['total_payments_count'], 1)
        self.assertEqual(res.context['total_outstanding'], Decimal('300.00'))
        self.assertEqual(res.context['overdue_invoices_count'], 1)
        self.assertEqual(len(res.context['page_obj']), 1)

    def test_seed_bulk_command(self):
        from django.core.management import call_command
        import time

        call_command('seed_bulk')
        self.assertEqual(Subscription.objects.count(), 5000)
        self.assertEqual(User.objects.filter(role=User.ROLE_CUSTOMER).count(), 200)
        self.assertEqual(Invoice.objects.count(), 4000)
        self.assertGreater(Payment.objects.count(), 1000)

        # Time all 3 pages
        self.client.force_login(self.admin)

        for url in ['/dashboard/', '/billing/', '/subscriptions/']:
            start = time.perf_counter()
            res = self.client.get(url)
            elapsed = time.perf_counter() - start
            self.assertEqual(res.status_code, 200)
            self.assertLess(elapsed, 1.0, f"{url} took {elapsed:.2f}s, exceeding 1.0s limit!")

