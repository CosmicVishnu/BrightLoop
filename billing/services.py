from decimal import Decimal
import datetime
from django.utils import timezone
from django.db import transaction
from .models import Invoice, InvoiceLine
from catalog.models import Discount

def calculate_period_end(period_start, billing_period):
    if billing_period == 'daily':
        return period_start + datetime.timedelta(days=1)
    elif billing_period == 'weekly':
        return period_start + datetime.timedelta(days=7)
    elif billing_period == 'yearly':
        return period_start + datetime.timedelta(days=365)
    else:  # monthly default
        return period_start + datetime.timedelta(days=30)

def calculate_due_date(period_start, payment_terms):
    if payment_terms == 'Net 15':
        return period_start + datetime.timedelta(days=15)
    elif payment_terms == 'Net 30':
        return period_start + datetime.timedelta(days=30)
    elif payment_terms == 'Net 60':
        return period_start + datetime.timedelta(days=60)
    else:  # Immediate
        return period_start

def generate_invoice(subscription, period_start=None):
    """
    Generate an invoice for a subscription:
    - Copies subscription lines to invoice lines
    - Computes subtotal
    - Applies best qualifying discount (checks dates, min qty/purchase, limit; increments used_count)
    - Applies taxes
    - Sets period and due date
    - Advances subscription next_billing_date
    - Idempotent: checks for unique constraint (subscription, period_start)
    """
    if period_start is None:
        period_start = subscription.next_billing_date or subscription.start_date or timezone.now().date()

    # Idempotency check: don't bill the same period twice
    existing = Invoice.objects.filter(subscription=subscription, period_start=period_start).first()
    if existing:
        return existing

    period_end = calculate_period_end(period_start, subscription.plan.billing_period)
    due_date = calculate_due_date(period_start, subscription.payment_terms)

    lines = list(subscription.lines.select_related('product', 'variant', 'tax').all())
    subtotal = sum((line.amount for line in lines), Decimal('0.00'))
    total_qty = sum((line.quantity for line in lines), 0)

    # Find applicable discounts
    best_discount = None
    best_discount_amount = Decimal('0.00')

    active_discounts = Discount.objects.prefetch_related('products').all()
    for disc in active_discounts:
        if not disc.is_currently_valid(period_start):
            continue

        if disc.applies_to_whole_subscription:
            qualifying_subtotal = subtotal
            qualifying_qty = total_qty
        else:
            disc_product_ids = set(disc.products.values_list('id', flat=True))
            qualifying_lines = [l for l in lines if l.product_id in disc_product_ids]
            qualifying_subtotal = sum((l.amount for l in qualifying_lines), Decimal('0.00'))
            qualifying_qty = sum((l.quantity for l in qualifying_lines), 0)

        if qualifying_subtotal < disc.min_purchase:
            continue
        if qualifying_qty < disc.min_quantity:
            continue

        if disc.type == Discount.TYPE_PERCENTAGE:
            disc_amt = (qualifying_subtotal * (disc.value / Decimal('100.00'))).quantize(Decimal('0.01'))
        else:
            disc_amt = min(disc.value, qualifying_subtotal).quantize(Decimal('0.01'))

        if disc_amt > best_discount_amount:
            best_discount_amount = disc_amt
            best_discount = disc

    # Apply best discount
    if best_discount and best_discount_amount > Decimal('0.00'):
        best_discount.used_count += 1
        best_discount.save(update_fields=['used_count'])

    # Compute tax amounts per line
    total_tax = Decimal('0.00')
    line_data = []

    if best_discount and not best_discount.applies_to_whole_subscription:
        disc_prod_ids = set(best_discount.products.values_list('id', flat=True))
        qualifying_sub = sum((l.amount for l in lines if l.product_id in disc_prod_ids), Decimal('0.00'))
        prod_ratio = (best_discount_amount / qualifying_sub) if qualifying_sub > Decimal('0.00') else Decimal('0.00')
        for line in lines:
            if line.product_id in disc_prod_ids:
                line_disc = (line.amount * prod_ratio).quantize(Decimal('0.01'))
            else:
                line_disc = Decimal('0.00')
            taxable_amt = max(Decimal('0.00'), line.amount - line_disc)
            if line.tax and line.tax.percentage > Decimal('0.00'):
                line_tax = (taxable_amt * (line.tax.percentage / Decimal('100.00'))).quantize(Decimal('0.01'))
            else:
                line_tax = Decimal('0.00')

            total_tax += line_tax
            line_data.append({
                'product': line.product,
                'variant': line.variant,
                'quantity': line.quantity,
                'unit_price': line.unit_price,
                'tax': line.tax,
                'tax_amount': line_tax,
                'amount': line.amount,
            })
    else:
        discount_ratio = (best_discount_amount / subtotal) if subtotal > Decimal('0.00') else Decimal('0.00')
        for line in lines:
            line_disc = (line.amount * discount_ratio).quantize(Decimal('0.01'))
            taxable_amt = max(Decimal('0.00'), line.amount - line_disc)
            if line.tax and line.tax.percentage > Decimal('0.00'):
                line_tax = (taxable_amt * (line.tax.percentage / Decimal('100.00'))).quantize(Decimal('0.01'))
            else:
                line_tax = Decimal('0.00')

            total_tax += line_tax
            line_data.append({
                'product': line.product,
                'variant': line.variant,
                'quantity': line.quantity,
                'unit_price': line.unit_price,
                'tax': line.tax,
                'tax_amount': line_tax,
                'amount': line.amount,
            })

    total = max(Decimal('0.00'), subtotal - best_discount_amount + total_tax).quantize(Decimal('0.01'))

    with transaction.atomic():
        invoice = Invoice.objects.create(
            subscription=subscription,
            customer=subscription.customer,
            period_start=period_start,
            period_end=period_end,
            status=Invoice.STATUS_DRAFT,
            subtotal=subtotal.quantize(Decimal('0.01')),
            discount_amount=best_discount_amount.quantize(Decimal('0.01')),
            tax_amount=total_tax.quantize(Decimal('0.01')),
            total=total,
            due_date=due_date,
        )

        for ld in line_data:
            InvoiceLine.objects.create(
                invoice=invoice,
                product=ld['product'],
                variant=ld['variant'],
                quantity=ld['quantity'],
                unit_price=ld['unit_price'],
                tax=ld['tax'],
                tax_amount=ld['tax_amount'],
                amount=ld['amount'],
            )

        # Advance next_billing_date
        subscription.next_billing_date = period_end
        subscription.save(update_fields=['next_billing_date', 'updated_at'])

    return invoice
