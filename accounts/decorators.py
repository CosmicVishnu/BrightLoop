from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not (request.user.role == 'admin' or request.user.is_superuser):
            messages.error(request, "Access denied: Admin privileges required.")
            raise PermissionDenied("Admin privileges required.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def staff_or_admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not (request.user.role in ['admin', 'staff'] or request.user.is_superuser):
            messages.error(request, "Access denied: Staff or Admin privileges required.")
            raise PermissionDenied("Staff or Admin privileges required.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def customer_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
