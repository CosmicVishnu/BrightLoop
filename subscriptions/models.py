from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from catalog.models import Plan, Product, Variant, Tax

class QuotationTemplate(models.Model):
    name = models.CharField(max_length=150)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='quotation_templates')
    validity_days = models.PositiveIntegerField(default=30)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.plan.name})"


class QuotationTemplateLine(models.Model):
    template = models.ForeignKey(QuotationTemplate, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class Subscription(models.Model):
    STATUS_DRAFT = 'Draft'
    STATUS_QUOTATION = 'Quotation'
    STATUS_CONFIRMED = 'Confirmed'
    STATUS_ACTIVE = 'Active'
    STATUS_PAUSED = 'Paused'
    STATUS_CLOSED = 'Closed'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_QUOTATION, 'Quotation'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_PAUSED, 'Paused'),
        (STATUS_CLOSED, 'Closed'),
    ]

    PAYMENT_TERMS_CHOICES = [
        ('Immediate', 'Immediate Payment'),
        ('Net 15', 'Net 15 Days'),
        ('Net 30', 'Net 30 Days'),
        ('Net 60', 'Net 60 Days'),
    ]

    number = models.CharField(max_length=32, unique=True, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        limit_choices_to={'role': 'customer'},
        db_index=True
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    start_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField(null=True, blank=True)
    payment_terms = models.CharField(max_length=50, choices=PAYMENT_TERMS_CHOICES, default='Immediate')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    next_billing_date = models.DateField(null=True, blank=True)
    template = models.ForeignKey(QuotationTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name='subscriptions')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f"{self.number} - {self.customer.email} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.number:
            last = Subscription.objects.order_by('-id').first()
            if last and last.id:
                next_id = last.id + 1
            else:
                next_id = 1
            self.number = f"SUB-{next_id:04d}"
        if not self.next_billing_date and self.status == self.STATUS_ACTIVE:
            self.next_billing_date = self.start_date
        super().save(*args, **kwargs)

    def check_and_auto_close(self):
        """Auto-close subscription if plan end date reached and auto_close is enabled."""
        today = timezone.now().date()
        if (self.plan.end_date and
            today > self.plan.end_date and
            self.plan.auto_close and
            self.status in [self.STATUS_ACTIVE, self.STATUS_PAUSED]):
            self.status = self.STATUS_CLOSED
            self.save(update_fields=['status', 'updated_at'])
            return True
        return False

    @property
    def total_recurring_amount(self):
        total = Decimal('0.00')
        for line in self.lines.all():
            total += line.amount
        return total

    # Validation of transitions
    def can_transition_to(self, target_status):
        self.check_and_auto_close()
        current = self.status
        today = timezone.now().date()

        if target_status == self.STATUS_QUOTATION:
            return current == self.STATUS_DRAFT
        elif target_status == self.STATUS_CONFIRMED:
            return current in [self.STATUS_DRAFT, self.STATUS_QUOTATION]
        elif target_status == self.STATUS_ACTIVE:
            if current == self.STATUS_CONFIRMED:
                return True
            if current == self.STATUS_PAUSED:
                return True
            if current == self.STATUS_CLOSED and self.plan.renewable:
                return True
            return False
        elif target_status == self.STATUS_PAUSED:
            return current == self.STATUS_ACTIVE and self.plan.pausable
        elif target_status == self.STATUS_CLOSED:
            # Plan closable flag governs closing before plan end date
            if current in [self.STATUS_ACTIVE, self.STATUS_PAUSED]:
                if self.plan.closable:
                    return True
                if self.plan.end_date and today >= self.plan.end_date:
                    return True
            return False
        return False


class SubscriptionLine(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(Variant, null=True, blank=True, on_delete=models.SET_NULL)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.ForeignKey(Tax, null=True, blank=True, on_delete=models.SET_NULL)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.product.name} ({self.quantity} x ₹{self.unit_price})"

    def save(self, *args, **kwargs):
        self.amount = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))
        super().save(*args, **kwargs)
