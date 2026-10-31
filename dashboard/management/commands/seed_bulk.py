import datetime
from decimal import Decimal
import random
import time
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.db import models, transaction, connection

from catalog.models import Product, Variant, Plan, Tax, Discount
from subscriptions.models import QuotationTemplate, QuotationTemplateLine, Subscription, SubscriptionLine
from billing.models import Invoice, InvoiceLine, Payment

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds database with 5,000 subscriptions spread across 200 customers, with invoices and payments using bulk_create.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-clean',
            action='store_true',
            help='Do not clear existing subscriptions, invoices, and payments before seeding.',
        )

    def handle(self, *args, **options):
        start_time = time.time()
        self.stdout.write("Starting high-performance bulk database seeding...")

        today = timezone.now().date()
        now = timezone.now()

        with transaction.atomic():
            # 1. Clean existing records if requested (default: clean for reproducible 5000 subs)
            if not options['no_clean']:
                self.stdout.write("Cleaning previous subscription and billing data...")
                Payment.objects.all().delete()
                InvoiceLine.objects.all().delete()
                Invoice.objects.all().delete()
                SubscriptionLine.objects.all().delete()
                Subscription.objects.all().delete()

            # 2. Ensure Admin and Staff
            self.stdout.write("Ensuring Admin & Staff users...")
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
            if not admin_user.check_password("Admin@1234"):
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
            if not staff_user.check_password("Staff@1234"):
                staff_user.set_password("Staff@1234")
                staff_user.save()

            # 3. Ensure 200 Customer Users using bulk_create
            self.stdout.write("Ensuring 200 customer users...")
            existing_customers = list(User.objects.filter(role=User.ROLE_CUSTOMER).order_by('id'))
            existing_count = len(existing_customers)
            needed_count = 200 - existing_count

            if needed_count > 0:
                hashed_pw = make_password("Customer@1234")
                new_users = []
                for i in range(1, needed_count + 1):
                    cust_num = existing_count + i
                    new_users.append(User(
                        email=f"customer{cust_num:03d}@brightloop-enterprise.com",
                        first_name=f"Customer{cust_num}",
                        last_name="Enterprise",
                        company_name=f"Client Organization {cust_num}",
                        role=User.ROLE_CUSTOMER,
                        password=hashed_pw,
                        is_active=True,
                    ))
                User.objects.bulk_create(new_users, batch_size=500, ignore_conflicts=True)
                existing_customers = list(User.objects.filter(role=User.ROLE_CUSTOMER).order_by('id')[:200])

            customers = existing_customers[:200]
            self.stdout.write(f"Loaded {len(customers)} customers.")

            # 4. Catalog: Taxes, Products, Variants, Plans
            self.stdout.write("Ensuring catalog items...")
            tax_std, _ = Tax.objects.get_or_create(
                name="Standard Sales Tax",
                defaults={"percentage": Decimal("8.00"), "is_active": True}
            )
            tax_vat, _ = Tax.objects.get_or_create(
                name="VAT / GST",
                defaults={"percentage": Decimal("18.00"), "is_active": True}
            )

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

            plan_monthly, _ = Plan.objects.get_or_create(
                name="Startup Monthly",
                defaults={
                    "price": Decimal("99.00"),
                    "billing_period": Plan.PERIOD_MONTHLY,
                    "min_quantity": 1,
                    "start_date": today - datetime.timedelta(days=365),
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
                    "start_date": today - datetime.timedelta(days=120),
                    "end_date": today - datetime.timedelta(days=10),
                    "closable": False,
                    "pausable": False,
                    "renewable": False,
                    "auto_close": True,
                }
            )

            plans_list = [plan_monthly, plan_annual, plan_pilot]
            terms_list = ['Immediate', 'Net 15', 'Net 30', 'Net 60']

            # 5. Build 5,000 Subscriptions
            self.stdout.write("Generating 5,000 subscriptions in memory...")
            statuses_distribution = [
                ('Active', 3000),
                ('Confirmed', 600),
                ('Quotation', 500),
                ('Closed', 400),
                ('Paused', 300),
                ('Draft', 200),
            ]

            status_list = []
            for status, count in statuses_distribution:
                status_list.extend([status] * count)

            # Determine start id
            last_sub = Subscription.objects.order_by('-id').first()
            start_sub_id = (last_sub.id if last_sub else 0) + 1

            subscriptions_to_create = []
            sub_meta_list = []  # helper to generate lines and invoices

            for i in range(5000):
                sub_id = start_sub_id + i
                status = status_list[i]
                customer = customers[i % len(customers)]

                # Pick plan: closed subscriptions can use legacy pilot
                if status == 'Closed' and i % 2 == 0:
                    plan = plan_pilot
                else:
                    plan = plans_list[i % len(plans_list)]

                terms = terms_list[i % len(terms_list)]

                # Vary start dates across the past 300 days
                days_ago = (i % 270) + 10
                start_date = today - datetime.timedelta(days=days_ago)

                if plan == plan_annual:
                    expiry_date = start_date + datetime.timedelta(days=365)
                elif plan.end_date:
                    expiry_date = plan.end_date
                else:
                    expiry_date = None

                # Compute next billing date
                if status == 'Active':
                    # Half are overdue or due today, half in future
                    offset = (i % 30) - 15
                    next_bill = today + datetime.timedelta(days=offset)
                elif status == 'Confirmed':
                    next_bill = today + datetime.timedelta(days=5)
                else:
                    next_bill = None

                sub = Subscription(
                    id=sub_id,
                    number=f"SUB-{sub_id:05d}",
                    customer_id=customer.id,
                    plan_id=plan.id,
                    start_date=start_date,
                    expiry_date=expiry_date,
                    payment_terms=terms,
                    status=status,
                    next_billing_date=next_bill,
                    created_at=now,
                    updated_at=now,
                )
                subscriptions_to_create.append(sub)
                sub_meta_list.append({
                    'sub_id': sub_id,
                    'customer_id': customer.id,
                    'plan': plan,
                    'status': status,
                    'start_date': start_date,
                    'terms': terms,
                    'index': i,
                })

            self.stdout.write("Inserting 5,000 subscriptions via bulk_create...")
            Subscription.objects.bulk_create(subscriptions_to_create, batch_size=1000)

            # 6. Build Subscription Lines
            self.stdout.write("Generating subscription lines...")
            sub_lines_to_create = []
            sub_line_specs_by_sub = {}

            for meta in sub_meta_list:
                sub_id = meta['sub_id']
                i = meta['index']

                specs = []
                # Line 1: ERP Core
                is_odoo = (i % 3 == 0)
                variant = v1_odoo if is_odoo else v1_native
                unit_price = Decimal("1760.00") if is_odoo else Decimal("1200.00")
                tax = tax_vat if i % 2 == 0 else tax_std
                qty = 1
                amt = unit_price * qty
                specs.append({
                    'product': p1,
                    'variant': variant,
                    'quantity': qty,
                    'unit_price': unit_price,
                    'tax': tax,
                    'amount': amt,
                })

                # Line 2 (half of the subs): User Seat Licenses
                if i % 2 == 0:
                    is_ent = (i % 4 == 0)
                    v2 = v2_ent if is_ent else v2_std
                    up2 = Decimal("80.00") if is_ent else Decimal("45.00")
                    q2 = (i % 5) + 3
                    amt2 = up2 * q2
                    specs.append({
                        'product': p2,
                        'variant': v2,
                        'quantity': q2,
                        'unit_price': up2,
                        'tax': tax,
                        'amount': amt2,
                    })

                # Line 3 (one third of the subs): SLA Support
                if i % 3 == 0:
                    is_247 = (i % 6 == 0)
                    v3 = v3_247 if is_247 else v3_biz
                    up3 = Decimal("500.00") if is_247 else Decimal("300.00")
                    q3 = 1
                    amt3 = up3 * q3
                    specs.append({
                        'product': p3,
                        'variant': v3,
                        'quantity': q3,
                        'unit_price': up3,
                        'tax': tax,
                        'amount': amt3,
                    })

                sub_line_specs_by_sub[sub_id] = specs

                for spec in specs:
                    sub_lines_to_create.append(SubscriptionLine(
                        subscription_id=sub_id,
                        product_id=spec['product'].id,
                        variant_id=spec['variant'].id if spec['variant'] else None,
                        quantity=spec['quantity'],
                        unit_price=spec['unit_price'],
                        tax_id=spec['tax'].id if spec['tax'] else None,
                        amount=spec['amount'],
                    ))

            self.stdout.write(f"Inserting {len(sub_lines_to_create)} subscription lines via bulk_create...")
            SubscriptionLine.objects.bulk_create(sub_lines_to_create, batch_size=2000)

            # 7. Build Invoices (for Active, Closed, and Confirmed subscriptions = 4,000 subscriptions)
            self.stdout.write("Generating invoices in memory...")
            last_inv = Invoice.objects.order_by('-id').first()
            start_inv_id = (last_inv.id if last_inv else 0) + 1

            invoices_to_create = []
            inv_lines_to_create = []
            payments_to_create = []

            inv_counter = 0

            for meta in sub_meta_list:
                status = meta['status']
                if status not in ['Active', 'Closed', 'Confirmed']:
                    continue

                inv_counter += 1
                inv_id = start_inv_id + inv_counter - 1
                sub_id = meta['sub_id']
                cust_id = meta['customer_id']
                start_date = meta['start_date']
                i = meta['index']

                specs = sub_line_specs_by_sub[sub_id]
                subtotal = sum(s['amount'] for s in specs)

                # Compute line taxes
                total_tax = Decimal("0.00")
                line_details = []
                for s in specs:
                    pct = s['tax'].percentage if s['tax'] else Decimal("0.00")
                    line_tax = (s['amount'] * pct / Decimal("100.00")).quantize(Decimal("0.01"))
                    total_tax += line_tax
                    line_details.append({
                        'product_id': s['product'].id,
                        'variant_id': s['variant'].id if s['variant'] else None,
                        'quantity': s['quantity'],
                        'unit_price': s['unit_price'],
                        'tax_id': s['tax'].id if s['tax'] else None,
                        'tax_amount': line_tax,
                        'amount': s['amount'],
                    })

                total = subtotal + total_tax

                # Scenarios across invoices
                scenario = inv_counter % 7
                # 0: Overdue Confirmed (unpaid)
                # 1: Overdue Confirmed (partially paid)
                # 2: Overdue Draft (unpaid)
                # 3: Paid (due in past)
                # 4: Paid (due in future)
                # 5: Future Confirmed (unpaid)
                # 6: Cancelled

                period_start = start_date
                period_end = start_date + datetime.timedelta(days=30)

                payment_to_add = None

                if scenario == 0:
                    inv_status = Invoice.STATUS_CONFIRMED
                    due_date = today - datetime.timedelta(days=25)
                elif scenario == 1:
                    inv_status = Invoice.STATUS_CONFIRMED
                    due_date = today - datetime.timedelta(days=15)
                    part_payment_amount = (total / Decimal("2.00")).quantize(Decimal("0.01"))
                    payment_to_add = Payment(
                        invoice_id=inv_id,
                        method='card',
                        amount=part_payment_amount,
                        date=due_date - datetime.timedelta(days=3),
                        note="Partial invoice installment",
                        created_at=now,
                    )
                elif scenario == 2:
                    inv_status = Invoice.STATUS_DRAFT
                    due_date = today - datetime.timedelta(days=7)
                elif scenario == 3:
                    inv_status = Invoice.STATUS_PAID
                    due_date = today - datetime.timedelta(days=12)
                    payment_to_add = Payment(
                        invoice_id=inv_id,
                        method='bank',
                        amount=total,
                        date=due_date - datetime.timedelta(days=2),
                        note="Settled via bank wire transfer",
                        created_at=now,
                    )
                elif scenario == 4:
                    inv_status = Invoice.STATUS_PAID
                    due_date = today + datetime.timedelta(days=14)
                    payment_to_add = Payment(
                        invoice_id=inv_id,
                        method='upi',
                        amount=total,
                        date=today - datetime.timedelta(days=1),
                        note="Direct UPI instant payment",
                        created_at=now,
                    )
                elif scenario == 5:
                    inv_status = Invoice.STATUS_CONFIRMED
                    due_date = today + datetime.timedelta(days=20)
                else:  # scenario 6
                    inv_status = Invoice.STATUS_CANCELLED
                    due_date = today - datetime.timedelta(days=5)

                invoice_obj = Invoice(
                    id=inv_id,
                    number=f"INV-{inv_id:05d}",
                    subscription_id=sub_id,
                    customer_id=cust_id,
                    period_start=period_start,
                    period_end=period_end,
                    status=inv_status,
                    subtotal=subtotal,
                    discount_amount=Decimal("0.00"),
                    tax_amount=total_tax,
                    total=total,
                    due_date=due_date,
                    notes=f"Auto-generated bulk invoice for SUB-{sub_id:05d}",
                    created_at=now,
                    updated_at=now,
                )
                invoices_to_create.append(invoice_obj)

                for ld in line_details:
                    inv_lines_to_create.append(InvoiceLine(
                        invoice_id=inv_id,
                        product_id=ld['product_id'],
                        variant_id=ld['variant_id'],
                        quantity=ld['quantity'],
                        unit_price=ld['unit_price'],
                        tax_id=ld['tax_id'],
                        tax_amount=ld['tax_amount'],
                        amount=ld['amount'],
                    ))

                if payment_to_add:
                    payments_to_create.append(payment_to_add)

            self.stdout.write(f"Inserting {len(invoices_to_create)} invoices via bulk_create...")
            Invoice.objects.bulk_create(invoices_to_create, batch_size=1000)

            self.stdout.write(f"Inserting {len(inv_lines_to_create)} invoice lines via bulk_create...")
            InvoiceLine.objects.bulk_create(inv_lines_to_create, batch_size=2000)

            self.stdout.write(f"Inserting {len(payments_to_create)} payments via bulk_create...")
            Payment.objects.bulk_create(payments_to_create, batch_size=2000)

            # Update sqlite sequence table so standard creates continue smoothly
            self.stdout.write("Synchronizing database sequence counters...")
            with connection.cursor() as cursor:
                try:
                    tables = [
                        ('subscriptions_subscription', Subscription),
                        ('subscriptions_subscriptionline', SubscriptionLine),
                        ('billing_invoice', Invoice),
                        ('billing_invoiceline', InvoiceLine),
                        ('billing_payment', Payment),
                    ]
                    for table_name, model in tables:
                        max_id = model.objects.aggregate(m=models.Max('id'))['m'] or 0
                        cursor.execute("UPDATE sqlite_sequence SET seq = ? WHERE name = ?", [max_id, table_name])
                except Exception:
                    pass

        elapsed = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded bulk dataset in {elapsed:.2f}s:\n"
            f"- Subscriptions: {Subscription.objects.count():,}\n"
            f"- Invoices: {Invoice.objects.count():,}\n"
            f"- Payments: {Payment.objects.count():,}\n"
            f"- Customers: {User.objects.filter(role=User.ROLE_CUSTOMER).count():,}"
        ))
