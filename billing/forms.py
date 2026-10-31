from django import forms
from .models import Payment

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['method', 'amount', 'date', 'note']
        widgets = {
            'method': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'note': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Transaction ID or memo'}),
        }
