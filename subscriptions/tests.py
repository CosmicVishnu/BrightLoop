import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from catalog.models import Plan, Product, Tax
from subscriptions.models import Subscription, SubscriptionLine

User = get_user_model()

class SubscriptionTransitionTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = User.objects.create_user(
            email='customer_sub@test.com',
            password='Customer#1234',
            role=User.ROLE_CUSTOMER
        )
        self.other_customer = User.objects.create_user(
            email='other_cust@test.com',
            password='Customer#1234',
            role=User.ROLE_CUSTOMER
        )
        self.plan = Plan.objects.create(
            name='Test Plan',
            price=Decimal('50.00'),
            billing_period=Plan.PERIOD_MONTHLY,
            min_quantity=1,
            closable=True,
            pausable=True,
            renewable=True
        )
        self.product = Product.objects.create(
            name='Cloud SaaS',
            sales_price=Decimal('50.00'),
            cost_price=Decimal('10.00')
        )

    def test_valid_transitions(self):
        sub = Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            status=Subscription.STATUS_DRAFT
        )
        # Draft -> Quotation: valid
        self.assertTrue(sub.can_transition_to(Subscription.STATUS_QUOTATION))
        # Draft -> Active: invalid jump
        self.assertFalse(sub.can_transition_to(Subscription.STATUS_ACTIVE))

        sub.status = Subscription.STATUS_QUOTATION
        self.assertTrue(sub.can_transition_to(Subscription.STATUS_CONFIRMED))

        sub.status = Subscription.STATUS_CONFIRMED
        self.assertTrue(sub.can_transition_to(Subscription.STATUS_ACTIVE))

        sub.status = Subscription.STATUS_ACTIVE
        self.assertTrue(sub.can_transition_to(Subscription.STATUS_PAUSED))
        self.assertTrue(sub.can_transition_to(Subscription.STATUS_CLOSED))

    def test_plan_flags_restricting_actions(self):
        restricted_plan = Plan.objects.create(
            name='Locked Plan',
            price=Decimal('100.00'),
            closable=False,
            pausable=False,
            renewable=False
        )
        sub = Subscription.objects.create(
            customer=self.customer,
            plan=restricted_plan,
            status=Subscription.STATUS_ACTIVE
        )
        self.assertFalse(sub.can_transition_to(Subscription.STATUS_PAUSED))
        self.assertFalse(sub.can_transition_to(Subscription.STATUS_CLOSED))

        sub.status = Subscription.STATUS_CLOSED
        self.assertFalse(sub.can_transition_to(Subscription.STATUS_ACTIVE))

    def test_auto_close_past_end_date(self):
        expired_plan = Plan.objects.create(
            name='Expired Plan',
            price=Decimal('10.00'),
            end_date=timezone.now().date() - datetime.timedelta(days=5),
            auto_close=True
        )
        sub = Subscription.objects.create(
            customer=self.customer,
            plan=expired_plan,
            status=Subscription.STATUS_ACTIVE
        )
        closed = sub.check_and_auto_close()
        self.assertTrue(closed)
        self.assertEqual(sub.status, Subscription.STATUS_CLOSED)

    def test_customer_portal_view_and_filtering(self):
        Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            status=Subscription.STATUS_ACTIVE
        )
        Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            status=Subscription.STATUS_QUOTATION
        )
        self.client.force_login(self.customer)
        res = self.client.get('/subscriptions/portal/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['total_subs_count'], 2)
        self.assertEqual(res.context['active_subs_count'], 1)

        # Status filter
        res_filter = self.client.get('/subscriptions/portal/?status=Quotation')
        self.assertEqual(res_filter.status_code, 200)
        self.assertEqual(len(res_filter.context['page_obj']), 1)

    def test_customer_browse_plans_creates_quotation(self):
        self.client.force_login(self.customer)
        res_get = self.client.get('/subscriptions/browse-plans/')
        self.assertEqual(res_get.status_code, 200)

        res_post = self.client.post('/subscriptions/browse-plans/', {
            'plan_id': self.plan.id,
            'quantity': 3,
            'payment_terms': 'Net 15',
            'notes': 'Test order from customer',
        })
        self.assertEqual(res_post.status_code, 302)
        created_sub = Subscription.objects.filter(customer=self.customer, status=Subscription.STATUS_QUOTATION).first()
        self.assertIsNotNone(created_sub)
        self.assertEqual(created_sub.payment_terms, 'Net 15')
        self.assertEqual(created_sub.lines.count(), 1)
        self.assertEqual(created_sub.lines.first().quantity, 3)

    def test_customer_security_404_on_other_subscription(self):
        # other customer owns this subscription
        other_sub = Subscription.objects.create(
            customer=self.other_customer,
            plan=self.plan,
            status=Subscription.STATUS_ACTIVE
        )
        self.client.force_login(self.customer)

        # Detail page returns 404
        res_detail = self.client.get(f'/subscriptions/{other_sub.id}/')
        self.assertEqual(res_detail.status_code, 404)

        # Transition endpoint returns 404
        res_trans = self.client.post(f'/subscriptions/{other_sub.id}/transition/Paused/')
        self.assertEqual(res_trans.status_code, 404)

    def test_customer_allowed_transitions_with_flags(self):
        sub = Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            status=Subscription.STATUS_ACTIVE
        )
        self.client.force_login(self.customer)

        # Customer pauses pausable active subscription
        res = self.client.post(f'/subscriptions/{sub.id}/transition/Paused/')
        self.assertEqual(res.status_code, 302)
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.STATUS_PAUSED)

        # Customer closes closable subscription
        res = self.client.post(f'/subscriptions/{sub.id}/transition/Closed/')
        self.assertEqual(res.status_code, 302)
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.STATUS_CLOSED)

        # Customer renews renewable closed subscription
        res = self.client.post(f'/subscriptions/{sub.id}/transition/Active/')
        self.assertEqual(res.status_code, 302)
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.STATUS_ACTIVE)

        # Customer cannot directly make arbitrary jumps (e.g. to Draft)
        res_bad = self.client.post(f'/subscriptions/{sub.id}/transition/Draft/')
        self.assertEqual(res_bad.status_code, 302)
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.STATUS_ACTIVE)
