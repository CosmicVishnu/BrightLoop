import datetime
from decimal import Decimal
import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction

from catalog.models import Product, Variant, Plan, Tax, Discount
from subscriptions.models import QuotationTemplate, QuotationTemplateLine, Subscription, SubscriptionLine
from billing.models import Invoice, InvoiceLine, Payment
from billing.services import generate_invoice

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds database with demo users, catalog, ~30 subscriptions, invoices, and payments.'

    def handle(self, *args, **options):
        self.stdout.write("Starting database seeding for Brightloop Software...")

        today = timezone.now().date()

        with transaction.atomic():
            # 1. Users
            self.stdout.write("Creating Users...")
            admin_user, _ = User.objects.get_or_create(
                email="admin@brightloop.com",
                defaults={
                    "first_name": "Alice",
                    "last_name": "Administrator",
                    "role": User.ROLE_ADMIN,
                    "is_staff": True,
                    "is_superuser": True,
                }
            )
            admin_user.set_password("Admin@1234")
            admin_user.save()

            staff_user, _ = User.objects.get_or_create(
                email="staff@brightloop.com",
                defaults={
                    "first_name": "Bob",
                    "last_name": "Operations",
                    "role": User.ROLE_STAFF,
                    "is_staff": True,
                }
            )
            staff_user.set_password("Staff@1234")
            staff_user.save()

            customers_data = [
                ("customer1@acme.com", "Acme Corporation", "Charlie", "Acme"),
                ("customer2@globex.com", "Globex Industries", "Diana", "Globex"),
                ("customer3@stark.com", "Stark Logistics", "Edward", "Stark"),
                ("customer4@initech.com", "Initech Solutions", "Fiona", "Initech"),
                ("customer5@umbrella.com", "Umbrella Health", "George", "Umbrella"),
            ]
            customers = []
            for email, comp, fname, lname in customers_data:
                cust, _ = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "company_name": comp,
                        "first_name": fname,
                        "last_name": lname,
                        "role": User.ROLE_CUSTOMER,
                    }
                )
                cust.set_password("Customer@1234")
                cust.save()
                customers.append(cust)

            # 2. Taxes (2 taxes)
            self.stdout.write("Creating Taxes...")
            tax_std, _ = Tax.objects.get_or_create(
                name="Standard Sales Tax",
                defaults={"percentage": Decimal("8.00"), "is_active": True}
            )
            tax_vat, _ = Tax.objects.get_or_create(
                name="VAT / GST",
                defaults={"percentage": Decimal("18.00"), "is_active": True}
            )

            # 3. Products & Variants (3 products with variants)
            self.stdout.write("Creating Products & Variants...")
            p1, _ = Product.objects.get_or_create(
                name="BrightERP Cloud Core",
                defaults={
                    "type": "service",
                    "sales_price": Decimal("1200.00"),
                    "cost_price": Decimal("400.00"),
                    "notes": "Core ERP software instance with managed database hosting.",
                }
            )
            v1_odoo, _ = Variant.objects.get_or_create(
                product=p1, attribute="Brand", value="Odoo",
                defaults={"extra_price": Decimal("560.00")}
            )
            v1_native, _ = Variant.objects.get_or_create(
                product=p1, attribute="Brand", value="Brightloop Native",
                defaults={"extra_price": Decimal("0.00")}
            )

            p2, _ = Product.objects.get_or_create(
                name="User Seat License",
                defaults={
                    "type": "license",
                    "sales_price": Decimal("45.00"),
                    "cost_price": Decimal("12.00"),
                    "notes": "Named user seat license with single sign-on access.",
                }
            )
            v2_std, _ = Variant.objects.get_or_create(
                product=p2, attribute="Tier", value="Standard",
                defaults={"extra_price": Decimal("0.00")}
            )
            v2_ent, _ = Variant.objects.get_or_create(
                product=p2, attribute="Tier", value="Enterprise",
                defaults={"extra_price": Decimal("35.00")}
            )

            p3, _ = Product.objects.get_or_create(
                name="Priority SLA Support",
                defaults={
                    "type": "support",
                    "sales_price": Decimal("300.00"),
                    "cost_price": Decimal("80.00"),
                    "notes": "Guaranteed response time with direct engineering contact.",
                }
            )
            v3_biz, _ = Variant.objects.get_or_create(
                product=p3, attribute="Coverage", value="Business Hours",
                defaults={"extra_price": Decimal("0.00")}
            )
            v3_247, _ = Variant.objects.get_or_create(
                product=p3, attribute="Coverage", value="24/7 Dedicated",
                defaults={"extra_price": Decimal("200.00")}
            )

            # 4. Plans (3 plans)
            self.stdout.write("Creating Plans...")
            plan_monthly, _ = Plan.objects.get_or_create(
                name="Startup Monthly",
                defaults={
                    "price": Decimal("99.00"),
                    "billing_period": Plan.PERIOD_MONTHLY,
                    "min_quantity": 1,
                    "start_date": today - datetime.timedelta(days=180),
                    "closable": True,
                    "pausable": True,
                    "renewable": True,
                    "auto_close": False,
                }
            )
            plan_annual, _ = Plan.objects.get_or_create(
                name="Growth Annual",
                defaults={
                    "price": Decimal("999.00"),
                    "billing_period": Plan.PERIOD_YEARLY,
                    "min_quantity": 1,
                    "start_date": today - datetime.timedelta(days=365),
                    "closable": True,
                    "pausable": True,
                    "renewable": True,
                    "auto_close": False,
                }
            )
            plan_pilot, _ = Plan.objects.get_or_create(
                name="Legacy Pilot",
                defaults={
                    "price": Decimal("50.00"),
                    "billing_period": Plan.PERIOD_MONTHLY,
                    "min_quantity": 1,
                    "start_date": today - datetime.timedelta(days=90),
                    "end_date": today - datetime.timedelta(days=10),
                    "closable": False,
                    "pausable": False,
                    "renewable": False,
                    "auto_close": True,
                }
            )

            # 5. Discounts (2 discounts)
            self.stdout.write("Creating Discounts...")
            disc1, _ = Discount.objects.get_or_create(
                name="Volume Discount 10%",
                defaults={
                    "type": Discount.TYPE_PERCENTAGE,
                    "value": Decimal("10.00"),
                    "min_purchase": Decimal("400.00"),
                    "min_quantity": 2,
                    "applies_to_whole_subscription": True,
                    "start_date": today - datetime.timedelta(days=120),
                    "end_date": today + datetime.timedelta(days=120),
                    "usage_limit": 100,
                }
            )
            disc2, _ = Discount.objects.get_or_create(
                name="Welcome Voucher (₹100)",
                defaults={
                    "type": Discount.TYPE_FIXED,
                    "value": Decimal("100.00"),
                    "min_purchase": Decimal("250.00"),
                    "min_quantity": 1,
                    "applies_to_whole_subscription": True,
                    "start_date": today - datetime.timedelta(days=60),
                    "end_date": today + datetime.timedelta(days=60),
                    "usage_limit": 50,
                }
            )

            # 6. Quotation Templates
            self.stdout.write("Creating Quotation Templates...")
            tmpl_standard, _ = QuotationTemplate.objects.get_or_create(
                name="Standard ERP Starter Package",
                defaults={"plan": plan_monthly, "validity_days": 30}
            )
            if not tmpl_standard.lines.exists():
                QuotationTemplateLine.objects.create(template=tmpl_standard, product=p1, quantity=1)
                QuotationTemplateLine.objects.create(template=tmpl_standard, product=p2, quantity=5)

            tmpl_enterprise, _ = QuotationTemplate.objects.get_or_create(
                name="Enterprise Full Stack",
                defaults={"plan": plan_annual, "validity_days": 45}
            )
            if not tmpl_enterprise.lines.exists():
                QuotationTemplateLine.objects.create(template=tmpl_enterprise, product=p1, quantity=1)
                QuotationTemplateLine.objects.create(template=tmpl_enterprise, product=p2, quantity=20)
                QuotationTemplateLine.objects.create(template=tmpl_enterprise, product=p3, quantity=1)

            # 7. Subscriptions (~30 subscriptions with invoices & payments)
            self.stdout.write("Generating ~30 subscriptions with invoices and payments...")

            # Clean existing to prevent duplicates when re-seeding
            Payment.objects.all().delete()
            InvoiceLine.objects.all().delete()
            Invoice.objects.all().delete()
            SubscriptionLine.objects.all().delete()
            Subscription.objects.all().delete()

            plans_list = [plan_monthly, plan_annual, plan_pilot]
            terms_list = ['Immediate', 'Net 15', 'Net 30']

            # Target 30 subscriptions:
            # 18 Active, 4 Confirmed, 3 Quotation, 2 Draft, 2 Paused, 2 Closed = 31 total
            statuses_config = [
                ('Active', 18),
                ('Confirmed', 4),
                ('Quotation', 3),
                ('Draft', 2),
                ('Paused', 2),
                ('Closed', 2),
            ]

            sub_count = 0
            for status, count in statuses_config:
                for i in range(count):
                    sub_count += 1
                    customer = customers[(sub_count - 1) % len(customers)]
                    plan = plan_pilot if status == 'Closed' and i == 0 else plans_list[(sub_count - 1) % len(plans_list)]
                    terms = terms_list[(sub_count - 1) % len(terms_list)]

                    # Start dates varied across last 180 days
                    days_ago = (sub_count * 5) % 150 + 10
                    start_date = today - datetime.timedelta(days=days_ago)

                    # Compute next billing date
                    if status == 'Active':
                        next_bill = today - datetime.timedelta(days=(sub_count % 20))
                    elif status == 'Confirmed':
                        next_bill = today + datetime.timedelta(days=5)
                    else:
                        next_bill = None

                    sub = Subscription.objects.create(
                        customer=customer,
                        plan=plan,
                        start_date=start_date,
                        expiry_date=start_date + datetime.timedelta(days=365) if plan == plan_annual else None,
                        payment_terms=terms,
                        status=status,
                        next_billing_date=next_bill,
                        template=tmpl_standard if sub_count % 2 == 0 else None
                    )

                    # Add 1 to 3 lines
                    tax = tax_vat if sub_count % 2 == 0 else tax_std
                    SubscriptionLine.objects.create(
                        subscription=sub,
                        product=p1,
                        variant=v1_odoo if sub_count % 3 == 0 else v1_native,
                        quantity=1,
                        unit_price=v1_odoo.total_unit_price if sub_count % 3 == 0 else p1.sales_price,
                        tax=tax
                    )

                    if sub_count % 2 == 0:
                        SubscriptionLine.objects.create(
                            subscription=sub,
                            product=p2,
                            variant=v2_ent if sub_count % 4 == 0 else v2_std,
                            quantity=random.choice([3, 5, 10]),
                            unit_price=v2_ent.total_unit_price if sub_count % 4 == 0 else p2.sales_price,
                            tax=tax
                        )

                    if sub_count % 3 == 0:
                        SubscriptionLine.objects.create(
                            subscription=sub,
                            product=p3,
                            variant=v3_247 if sub_count % 6 == 0 else v3_biz,
                            quantity=1,
                            unit_price=v3_247.total_unit_price if sub_count % 6 == 0 else p3.sales_price,
                            tax=tax
                        )

                    # Invoices generation for Active, Closed, and some Confirmed
                    if status in ['Active', 'Closed'] or (status == 'Confirmed' and sub_count % 2 == 0):
                        # Generate initial invoice
                        inv = generate_invoice(sub, period_start=start_date)
                        if inv:
                            # Decide invoice scenario:
                            # Some Overdue (due_date < today and not Paid)
                            # Some Paid
                            # Some Partially Paid
                            # Some Draft / Confirmed

                            scenario = sub_count % 5
                            if scenario == 0:
                                # Overdue Confirmed invoice (past due_date, unpaid)
                                inv.period_start = today - datetime.timedelta(days=45)
                                inv.period_end = today - datetime.timedelta(days=15)
                                inv.due_date = today - datetime.timedelta(days=15)
                                inv.status = Invoice.STATUS_CONFIRMED
                                inv.save()
                            elif scenario == 1:
                                # Overdue Confirmed invoice (past due_date, partially paid)
                                inv.period_start = today - datetime.timedelta(days=35)
                                inv.period_end = today - datetime.timedelta(days=5)
                                inv.due_date = today - datetime.timedelta(days=10)
                                inv.status = Invoice.STATUS_CONFIRMED
                                inv.save()
                                part_amt = (inv.total / Decimal('2.00')).quantize(Decimal('0.01'))
                                Payment.objects.create(
                                    invoice=inv,
                                    method='card',
                                    amount=part_amt,
                                    date=inv.due_date - datetime.timedelta(days=2),
                                    note="Partial initial payment"
                                )
                            elif scenario == 2:
                                # Overdue Draft invoice
                                inv.period_start = today - datetime.timedelta(days=20)
                                inv.period_end = today + datetime.timedelta(days=10)
                                inv.due_date = today - datetime.timedelta(days=5)
                                inv.status = Invoice.STATUS_DRAFT
                                inv.save()
                            elif scenario == 3:
                                # Paid invoice
                                inv.period_start = today - datetime.timedelta(days=60)
                                inv.period_end = today - datetime.timedelta(days=30)
                                inv.due_date = today - datetime.timedelta(days=30)
                                inv.status = Invoice.STATUS_CONFIRMED
                                inv.save()
                                Payment.objects.create(
                                    invoice=inv,
                                    method='bank',
                                    amount=inv.total,
                                    date=inv.due_date - datetime.timedelta(days=5),
                                    note="Full wire payment received"
                                )
                            else:
                                # Recent Confirmed or Paid
                                inv.status = Invoice.STATUS_CONFIRMED
                                inv.due_date = today + datetime.timedelta(days=15)
                                inv.save()
                                if sub_count % 2 == 0:
                                    Payment.objects.create(
                                        invoice=inv,
                                        method='upi',
                                        amount=inv.total,
                                        date=today - datetime.timedelta(days=1),
                                        note="Paid via UPI"
                                    )

        self.stdout.write(self.style.SUCCESS(
            "Database seeding successfully completed!\n"
            f"Created: 1 Admin ({admin_user.email}), 1 Staff ({staff_user.email}), {len(customers)} Customers,\n"
            f"3 Products with Variants, 3 Plans, 2 Taxes, 2 Discounts,\n"
            f"{Subscription.objects.count()} Subscriptions, {Invoice.objects.count()} Invoices, {Payment.objects.count()} Payments."
        ))
