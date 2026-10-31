from django import forms
from django.contrib.auth import get_user_model, authenticate
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import AuthenticationForm as BaseAuthenticationForm
from .validators import BrightloopPasswordValidator

User = get_user_model()

class LoginForm(forms.Form):
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@example.com', 'autofocus': True})
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')

        if email and password:
            self.user_cache = authenticate(username=email, password=password)
            if self.user_cache is None:
                raise ValidationError("Invalid email or password.")
            elif not self.user_cache.is_active:
                raise ValidationError("This account is inactive.")
        return cleaned_data

    def get_user(self):
        return self.user_cache


class CustomerSignupForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=50, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=50, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'})
    )
    company_name = forms.CharField(
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company (optional)'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@example.com'})
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}),
        help_text="More than 8 characters, at least 1 uppercase, 1 lowercase, and 1 special character."
    )
    confirm_password = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm Password'})
    )

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'company_name']

    def clean_email(self):
        email = self.cleaned_data.get('email').strip().lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        validator = BrightloopPasswordValidator()
        validator.validate(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.ROLE_CUSTOMER
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class StaffCreationForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=50, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=50, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'staff@brightloop.com'})
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text="More than 8 characters, at least 1 uppercase, 1 lowercase, and 1 special character."
    )
    confirm_password = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name']

    def clean_email(self):
        email = self.cleaned_data.get('email').strip().lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        validator = BrightloopPasswordValidator()
        validator.validate(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.ROLE_STAFF
        user.is_staff = True
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user
