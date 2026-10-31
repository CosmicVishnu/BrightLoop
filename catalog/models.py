from django.db import models
from django.utils import timezone
from decimal import Decimal

class Product(models.Model):
    TYPE_CHOICES = [
        ('service', 'Service'),
        ('license', 'Software License'),
        ('hardware', 'Hardware/Goods'),
        ('support', 'Support & Maintenance'),
    ]

    name = models.CharField(max_length=150)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='service')
    sales_price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (${self.sales_price})"


class Variant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    attribute = models.CharField(max_length=100, help_text="e.g. Brand, Edition, Tier")
    value = models.CharField(max_length=100, help_text="e.g. Odoo, Enterprise, Pro")
    extra_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Added to base sales price")

    class Meta:
        ordering = ['product', 'attribute', 'value']
        unique_together = ('product', 'attribute', 'value')

    def __str__(self):
        sign = "+" if self.extra_price >= 0 else "-"
        return f"{self.product.name} - {self.attribute}: {self.value} ({sign}${abs(self.extra_price)})"

    @property
    def total_unit_price(self):
        return self.product.sales_price + self.extra_price


class Plan(models.Model):
    PERIOD_DAILY = 'daily'
    PERIOD_WEEKLY = 'weekly'
    PERIOD_MONTHLY = 'monthly'
    PERIOD_YEARLY = 'yearly'

    PERIOD_CHOICES = [
        (PERIOD_DAILY, 'Daily'),
        (PERIOD_WEEKLY, 'Weekly'),
        (PERIOD_MONTHLY, 'Monthly'),
        (PERIOD_YEARLY, 'Yearly'),
    ]

    name = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Base plan subscription price")
    billing_period = models.CharField(max_length=20, choices=PERIOD_CHOICES, default=PERIOD_MONTHLY)
    min_quantity = models.PositiveIntegerField(default=1)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    auto_close = models.BooleanField(default=False, help_text="Auto-close subscriptions when plan end date is reached")
    closable = models.BooleanField(default=True, help_text="Allow closing subscription before plan end date")
    pausable = models.BooleanField(default=True, help_text="Allow pausing the subscription")
    renewable = models.BooleanField(default=True, help_text="Allow renewing after expiry")

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (${self.price}/{self.get_billing_period_display()})"


class Tax(models.Model):
    name = models.CharField(max_length=100)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, help_text="Tax percentage, e.g. 18.00 for 18%")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'Taxes'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.percentage}%)"


class Discount(models.Model):
    TYPE_FIXED = 'fixed'
    TYPE_PERCENTAGE = 'percentage'

    TYPE_CHOICES = [
        (TYPE_FIXED, 'Fixed Amount ($)'),
        (TYPE_PERCENTAGE, 'Percentage (%)'),
    ]

    name = models.CharField(max_length=150)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_PERCENTAGE)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    min_purchase = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    min_quantity = models.PositiveIntegerField(default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Max times this discount can be applied")
    used_count = models.PositiveIntegerField(default=0)
    applies_to_whole_subscription = models.BooleanField(default=True, help_text="If checked, applies to whole order; otherwise only selected products")
    products = models.ManyToManyField(Product, blank=True, related_name='discounts', help_text="Specific products if not applying to whole subscription")

    class Meta:
        ordering = ['-id']

    def __str__(self):
        if self.type == self.TYPE_PERCENTAGE:
            val_str = f"{self.value}%"
        else:
            val_str = f"${self.value}"
        return f"{self.name} ({val_str} off)"

    def is_currently_valid(self, for_date=None):
        if for_date is None:
            for_date = timezone.now().date()
        if self.start_date and for_date < self.start_date:
            return False
        if self.end_date and for_date > self.end_date:
            return False
        if self.usage_limit is not None and self.used_count >= self.usage_limit:
            return False
        return True
