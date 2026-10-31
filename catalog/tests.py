from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
import datetime
from catalog.models import Product, Variant, Plan, Tax, Discount

User = get_user_model()

class CatalogTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser('admin@brightloop.test', 'Admin@1234')
        self.staff = User.objects.create_user('staff@brightloop.test', 'Staff@1234', role=User.ROLE_STAFF)
        self.customer = User.objects.create_user('cust@brightloop.test', 'Cust@1234', role=User.ROLE_CUSTOMER)

        self.product = Product.objects.create(
            name="ERP License",
            type="license",
            sales_price=Decimal("1000.00"),
            cost_price=Decimal("300.00")
        )
        self.variant = Variant.objects.create(
            product=self.product,
            attribute="Brand",
            value="Odoo",
            extra_price=Decimal("560.00")
        )

    def test_variant_price_calculation(self):
        self.assertEqual(self.variant.total_unit_price, Decimal("1560.00"))

    def test_discount_validity(self):
        today = timezone.now().date()
        disc = Discount.objects.create(
            name="Limited Promo",
            type=Discount.TYPE_PERCENTAGE,
            value=Decimal("15.00"),
            usage_limit=1,
            used_count=0,
            start_date=today - datetime.timedelta(days=2),
            end_date=today + datetime.timedelta(days=2),
        )
        self.assertTrue(disc.is_currently_valid())

        disc.used_count = 1
        self.assertFalse(disc.is_currently_valid())

    def test_staff_cannot_access_taxes_or_discounts(self):
        self.client.force_login(self.staff)

        res_tax = self.client.get('/catalog/taxes/')
        self.assertEqual(res_tax.status_code, 403)

        res_disc = self.client.get('/catalog/discounts/')
        self.assertEqual(res_disc.status_code, 403)

    def test_admin_can_access_taxes_and_discounts(self):
        self.client.force_login(self.admin)

        res_tax = self.client.get('/catalog/taxes/')
        self.assertEqual(res_tax.status_code, 200)

        res_disc = self.client.get('/catalog/discounts/')
        self.assertEqual(res_disc.status_code, 200)
