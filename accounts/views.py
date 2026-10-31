from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import CustomerSignupForm, StaffCreationForm, LoginForm
from .models import User
from .decorators import admin_required

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:login_redirect')

    if request.method == 'POST':
        form = CustomerSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to Brightloop Software, {user.first_name}!")
            return redirect('subscriptions:customer_portal')
    else:
        form = CustomerSignupForm()

    return render(request, 'accounts/signup.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:login_redirect')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('accounts:login_redirect')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('accounts:login')


@login_required
def login_redirect_view(request):
    if request.user.role == User.ROLE_CUSTOMER:
        return redirect('subscriptions:customer_portal')
    return redirect('dashboard:index')


@admin_required
def staff_list_create_view(request):
    if request.method == 'POST':
        form = StaffCreationForm(request.POST)
        if form.is_valid():
            staff_user = form.save()
            messages.success(request, f"Staff member '{staff_user.email}' created successfully.")
            return redirect('accounts:staff_management')
    else:
        form = StaffCreationForm()

    staff_members = User.objects.filter(role=User.ROLE_STAFF).order_by('-date_joined')
    admins = User.objects.filter(role=User.ROLE_ADMIN).order_by('-date_joined')
    customers_count = User.objects.filter(role=User.ROLE_CUSTOMER).count()

    context = {
        'form': form,
        'staff_members': staff_members,
        'admins': admins,
        'customers_count': customers_count,
    }
    return render(request, 'accounts/staff_management.html', context)
