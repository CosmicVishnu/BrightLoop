from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.utils import timezone
from django.core.paginator import Paginator
from accounts.decorators import staff_or_admin_required
from subscriptions.models import Subscription
from billing.models import Invoice, Payment

User = get_user_model()

@staff_or_admin_required
def dashboard_view(request):
    today = timezone.now().date()

    # Core Metrics
    active_subscriptions_count = Subscription.objects.filter(
        status=Subscription.STATUS_ACTIVE
    ).count()

    total_revenue_collected = Payment.objects.aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    # Total outstanding on non-paid, non-cancelled invoices
    active_invoices_sum = Invoice.objects.exclude(
        status__in=[Invoice.STATUS_CANCELLED, Invoice.STATUS_PAID]
    ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')

    paid_on_active_invoices = Payment.objects.filter(
        invoice__status__in=[Invoice.STATUS_CONFIRMED, Invoice.STATUS_DRAFT]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    total_outstanding = max(Decimal('0.00'), active_invoices_sum - paid_on_active_invoices)

    # Total payments recorded
    total_payments_count = Payment.objects.count()

    # Overdue invoices count
    overdue_invoices_count = Invoice.objects.filter(
        due_date__lt=today
    ).exclude(status__in=[Invoice.STATUS_PAID, Invoice.STATUS_CANCELLED]).count()

    # Overdue Invoices Query with filters
    overdue_queryset = Invoice.objects.filter(
        due_date__lt=today
    ).exclude(
        status__in=[Invoice.STATUS_PAID, Invoice.STATUS_CANCELLED]
    ).select_related('customer', 'subscription').prefetch_related('payments')

    # Filters
    customer_id = request.GET.get('customer')
    status_filter = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if customer_id:
        overdue_queryset = overdue_queryset.filter(customer_id=customer_id)
    if status_filter:
        overdue_queryset = overdue_queryset.filter(status=status_filter)
    if date_from:
        overdue_queryset = overdue_queryset.filter(due_date__gte=date_from)
    if date_to:
        overdue_queryset = overdue_queryset.filter(due_date__lte=date_to)

    # Pagination
    paginator = Paginator(overdue_queryset.order_by('due_date'), 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Customers for filter dropdown
    customers = User.objects.filter(role=User.ROLE_CUSTOMER).only('id', 'email', 'first_name', 'last_name').order_by('email')

    context = {
        'active_subscriptions_count': active_subscriptions_count,
        'total_revenue_collected': total_revenue_collected,
        'total_payments_count': total_payments_count,
        'total_outstanding': total_outstanding,
        'overdue_invoices_count': overdue_invoices_count,
        'page_obj': page_obj,
        'customers': customers,
        'selected_customer': customer_id,
        'selected_status': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'today': today,
    }
    return render(request, 'dashboard/index.html', context)
