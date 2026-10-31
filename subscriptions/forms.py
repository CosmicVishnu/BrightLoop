from django import forms
from django.contrib.auth import get_user_model
from .models import QuotationTemplate, QuotationTemplateLine, Subscription, SubscriptionLine
from catalog.models import Plan, Product, Variant, Tax

User = get_user_model()

class QuotationTemplateForm(forms.ModelForm):
    class Meta:
        model = QuotationTemplate
        fields = ['name', 'plan', 'validity_days', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Standard SaaS Package'}),
            'plan': forms.Select(attrs={'class': 'form-select'}),
            'validity_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class QuotationTemplateLineForm(forms.ModelForm):
    class Meta:
        model = QuotationTemplateLine
        fields = ['product', 'quantity']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'value': 1}),
        }


class SubscriptionCreateForm(forms.ModelForm):
    customer = forms.ModelChoiceField(
        queryset=User.objects.filter(role=User.ROLE_CUSTOMER).order_by('email'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Customer"
    )

    class Meta:
        model = Subscription
        fields = ['customer', 'plan', 'template', 'start_date', 'expiry_date', 'payment_terms', 'notes']
        widgets = {
            'plan': forms.Select(attrs={'class': 'form-select'}),
            'template': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'payment_terms': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class SubscriptionLineForm(forms.ModelForm):
    class Meta:
        model = SubscriptionLine
        fields = ['product', 'variant', 'quantity', 'unit_price', 'tax']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'variant': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'tax': forms.Select(attrs={'class': 'form-select'}),
        }
