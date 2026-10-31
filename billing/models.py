from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from subscriptions.models import Subscription
from catalog.models import Product, Variant, Tax

class Invoice(models.Model):
    STATUS_DRAFT = 'Draft'
    STATUS_CONFIRMED = 'Confirmed'
    STATUS_PAID = 'Paid'
    STATUS_CANCELLED = 'Cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_PAID, 'Paid'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    number = models.CharField(max_length=32, unique=True, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, related_name='invoices')
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='invoices',
        db_index=True
    )
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    due_date = models.DateField(db_index=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['subscription', 'period_start'],
                name='unique_subscription_period_start'
            )
        ]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['due_date']),
            models.Index(fields=['customer']),
            models.Index(fields=['status', 'due_date']),
        ]

    def __str__(self):
        return f"{self.number} - {self.customer.email} (${self.total}) [{self.status}]"

    def save(self, *args, **kwargs):
        if not self.number:
            last = Invoice.objects.order_by('-id').first()
            if last and last.id:
                next_id = last.id + 1
            else:
                next_id = 1
            self.number = f"INV-{next_id:04d}"
        super().save(*args, **kwargs)

    @property
    def total_paid(self):
        payments = self.payments.all()
        return sum(p.amount for p in payments) if payments else Decimal('0.00')

    @property
    def outstanding_balance(self):
        balance = self.total - self.total_paid
        return max(Decimal('0.00'), balance)

    @property
    def is_overdue(self):
        today = timezone.now().date()
        return self.status != self.STATUS_PAID and self.status != self.STATUS_CANCELLED and self.due_date < today

    def update_payment_status(self):
        """Update invoice status based on recorded payments."""
        if self.status == self.STATUS_CANCELLED:
            return
        paid = self.total_paid
        if paid >= self.total and self.total > 0:
            self.status = self.STATUS_PAID
        elif paid > 0 and self.status == self.STATUS_DRAFT:
            self.status = self.STATUS_CONFIRMED
        self.save(update_fields=['status', 'updated_at'])


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(Variant, null=True, blank=True, on_delete=models.SET_NULL)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.ForeignKey(Tax, null=True, blank=True, on_delete=models.SET_NULL)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.product.name} ({self.quantity} x ${self.unit_price})"


class Payment(models.Model):
    METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Credit/Debit Card'),
        ('upi', 'UPI'),
        ('bank', 'Bank Transfer'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='card')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(default=timezone.now)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"Payment {self.id} for {self.invoice.number} - ${self.amount} via {self.get_method_display()}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invoice.update_payment_status()
