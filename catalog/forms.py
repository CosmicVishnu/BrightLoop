from django import forms
from .models import Product, Variant, Plan, Tax, Discount

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'type', 'sales_price', 'cost_price', 'notes', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Enterprise ERP License'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'sales_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cost_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class VariantForm(forms.ModelForm):
    class Meta:
        model = Variant
        fields = ['product', 'attribute', 'value', 'extra_price']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'attribute': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Brand, Tier, Edition'}),
            'value': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Odoo, Pro, Gold'}),
            'extra_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class PlanForm(forms.ModelForm):
    class Meta:
        model = Plan
        fields = [
            'name', 'price', 'billing_period', 'min_quantity',
            'start_date', 'end_date', 'auto_close', 'closable',
            'pausable', 'renewable'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Professional Monthly Plan'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'billing_period': forms.Select(attrs={'class': 'form-select'}),
            'min_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'auto_close': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'closable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'pausable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'renewable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TaxForm(forms.ModelForm):
    class Meta:
        model = Tax
        fields = ['name', 'percentage', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. GST 18%, VAT 5%'}),
            'percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '18.00'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DiscountForm(forms.ModelForm):
    class Meta:
        model = Discount
        fields = [
            'name', 'type', 'value', 'min_purchase', 'min_quantity',
            'start_date', 'end_date', 'usage_limit',
            'applies_to_whole_subscription', 'products'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Early Bird 10% Off'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'min_purchase': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'min_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'usage_limit': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank for unlimited'}),
            'applies_to_whole_subscription': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'products': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 4}),
        }
