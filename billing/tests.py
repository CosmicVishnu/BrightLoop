import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.utils import IntegrityError
from catalog.models import Product, Variant, Plan, Tax, Discount
from subscriptions.models import Subscription, SubscriptionLine
from billing.models import Invoice, Payment
from billing.services import generate_invoice

User = get_user_model()

class BillingServiceTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = User.objects.create_user(
            email='testcust@example.com',
            password='Password@123',
            role=User.ROLE_CUSTOMER
        )
        self.other_customer = User.objects.create_user(
            email='othercust@example.com',
            password='Password@123',
            role=User.ROLE_CUSTOMER
        )
        self.plan = Plan.objects.create(
            name='Monthly Standard',
            price=Decimal('100.00'),
            billing_period=Plan.PERIOD_MONTHLY,
            closable=True,
            pausable=True,
            renewable=True
        )
        self.product = Product.objects.create(
            name='Cloud App',
            sales_price=Decimal('500.00'),
            cost_price=Decimal('100.00')
        )
        self.variant = Variant.objects.create(
            product=self.product,
            attribute='Brand',
            value='Odoo',
            extra_price=Decimal('560.00')
        )
        self.tax = Tax.objects.create(name='GST 10%', percentage=Decimal('10.00'))

        self.subscription = Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            start_date=timezone.now().date(),
            status=Subscription.STATUS_ACTIVE
        )
        SubscriptionLine.objects.create(
            subscription=self.subscription,
            product=self.product,
            variant=self.variant,
            quantity=1,
            unit_price=self.variant.total_unit_price,
            tax=self.tax
        )

    def test_generate_invoice_calculation(self):
        invoice = generate_invoice(self.subscription)
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.subtotal, Decimal('1060.00'))
        self.assertEqual(invoice.tax_amount, Decimal('106.00'))
        self.assertEqual(invoice.total, Decimal('1166.00'))
        self.assertEqual(invoice.status, Invoice.STATUS_DRAFT)
        self.assertEqual(invoice.outstanding_balance, Decimal('1166.00'))

    def test_invoice_idempotency_and_unique_constraint(self):
        inv1 = generate_invoice(self.subscription)
        inv2 = generate_invoice(self.subscription, period_start=inv1.period_start)
        self.assertEqual(inv1.id, inv2.id)

        with self.assertRaises(IntegrityError):
            Invoice.objects.create(
                subscription=self.subscription,
                customer=self.customer,
                period_start=inv1.period_start,
                period_end=inv1.period_end,
                status=Invoice.STATUS_DRAFT,
                subtotal=Decimal('100.00'),
                total=Decimal('100.00'),
                due_date=inv1.due_date
            )

    def test_payment_updates_status_to_paid(self):
        invoice = generate_invoice(self.subscription)
        invoice.status = Invoice.STATUS_CONFIRMED
        invoice.save()

        # Partial payment
        Payment.objects.create(
            invoice=invoice,
            method='card',
            amount=Decimal('600.00'),
            date=timezone.now().date()
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.STATUS_CONFIRMED)
        self.assertEqual(invoice.outstanding_balance, Decimal('566.00'))

        # Remaining payment
        Payment.objects.create(
            invoice=invoice,
            method='upi',
            amount=Decimal('566.00'),
            date=timezone.now().date()
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.STATUS_PAID)
        self.assertEqual(invoice.outstanding_balance, Decimal('0.00'))

    def test_discount_application(self):
        Discount.objects.create(
            name='Promo 10%',
            type=Discount.TYPE_PERCENTAGE,
            value=Decimal('10.00'),
            min_purchase=Decimal('500.00'),
            applies_to_whole_subscription=True
        )
        sub2 = Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            start_date=timezone.now().date() + datetime.timedelta(days=1),
            status=Subscription.STATUS_ACTIVE
        )
        SubscriptionLine.objects.create(
            subscription=sub2,
            product=self.product,
            quantity=1,
            unit_price=Decimal('1000.00'),
            tax=self.tax
        )
        inv = generate_invoice(sub2)
        self.assertEqual(inv.subtotal, Decimal('1000.00'))
        self.assertEqual(inv.discount_amount, Decimal('100.00'))
        self.assertEqual(inv.tax_amount, Decimal('90.00'))
        self.assertEqual(inv.total, Decimal('990.00'))

    def test_customer_invoices_view_metrics_and_filter(self):
        today = timezone.now().date()
        inv1 = generate_invoice(self.subscription)
        inv1.status = Invoice.STATUS_CONFIRMED
        inv1.due_date = today - datetime.timedelta(days=5)  # Overdue
        inv1.save()

        Payment.objects.create(
            invoice=inv1,
            method='card',
            amount=Decimal('200.00'),
            date=today
        )

        self.client.force_login(self.customer)
        res = self.client.get('/billing/my-invoices/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['total_paid'], Decimal('200.00'))
        self.assertEqual(res.context['total_outstanding'], Decimal('966.00'))
        self.assertEqual(res.context['overdue_count'], 1)

        # Status filter
        res_filter = self.client.get('/billing/my-invoices/?status=Paid')
        self.assertEqual(res_filter.status_code, 200)
        self.assertEqual(len(res_filter.context['page_obj']), 0)

    def test_customer_security_404_on_other_invoices(self):
        other_sub = Subscription.objects.create(
            customer=self.other_customer,
            plan=self.plan,
            status=Subscription.STATUS_ACTIVE
        )
        SubscriptionLine.objects.create(
            subscription=other_sub,
            product=self.product,
            quantity=1,
            unit_price=Decimal('200.00')
        )
        other_inv = generate_invoice(other_sub)

        self.client.force_login(self.customer)

        # Detail returns 404
        res_detail = self.client.get(f'/billing/{other_inv.id}/')
        self.assertEqual(res_detail.status_code, 404)

        # Print returns 404
        res_print = self.client.get(f'/billing/{other_inv.id}/print/')
        self.assertEqual(res_print.status_code, 404)

        # Payment on other's invoice returns 404
        res_pay = self.client.post(f'/billing/{other_inv.id}/pay/', {
            'method': 'card',
            'amount': '50.00',
            'date': timezone.now().date().isoformat()
        })
        self.assertEqual(res_pay.status_code, 404)

    def test_customer_pay_now_form(self):
        invoice = generate_invoice(self.subscription)
        invoice.status = Invoice.STATUS_CONFIRMED
        invoice.save()

        self.client.force_login(self.customer)

        # Customer pays full amount
        res_pay = self.client.post(f'/billing/{invoice.id}/pay/', {
            'method': 'upi',
            'amount': str(invoice.total),
            'date': timezone.now().date().isoformat(),
            'note': 'Customer online payment'
        })
        self.assertEqual(res_pay.status_code, 302)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.STATUS_PAID)
        self.assertEqual(invoice.outstanding_balance, Decimal('0.00'))
