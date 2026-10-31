from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum
from accounts.decorators import staff_or_admin_required
from .models import Invoice, Payment
from .forms import PaymentForm
from .services import generate_invoice
from subscriptions.models import Subscription

@staff_or_admin_required
def invoice_list_view(request):
    status_filter = request.GET.get('status', '')
    query = request.GET.get('q', '')

    queryset = Invoice.objects.select_related('customer', 'subscription').prefetch_related('payments').all()

    if status_filter:
        queryset = queryset.filter(status=status_filter)
    if query:
        queryset = queryset.filter(customer__email__icontains=query) | queryset.filter(number__icontains=query)

    paginator = Paginator(queryset, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'billing/invoice_list.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'query': query,
    })


@login_required
def invoice_detail_view(request, pk):
    # Security: customers can ONLY access their own invoices; return 404 for other IDs
    if request.user.role == 'customer':
        invoice = get_object_or_404(
            Invoice.objects.select_related('customer', 'subscription__plan')
            .prefetch_related('lines__product', 'lines__variant', 'lines__tax', 'payments'),
            pk=pk,
            customer=request.user
        )
    else:
        invoice = get_object_or_404(
            Invoice.objects.select_related('customer', 'subscription__plan')
            .prefetch_related('lines__product', 'lines__variant', 'lines__tax', 'payments'),
            pk=pk
        )

    payment_form = PaymentForm(
        initial={'amount': invoice.outstanding_balance, 'date': timezone.now().date()}
    ) if invoice.status != Invoice.STATUS_CANCELLED else None

    return render(request, 'billing/invoice_detail.html', {
        'invoice': invoice,
        'payment_form': payment_form,
        'is_customer': request.user.role == 'customer',
    })


@staff_or_admin_required
def generate_single_invoice_view(request, subscription_pk):
    if request.method != 'POST':
        return redirect('subscriptions:subscription_detail', pk=subscription_pk)

    sub = get_object_or_404(Subscription, pk=subscription_pk)
    if sub.status != Subscription.STATUS_ACTIVE:
        messages.error(request, "Invoices can only be generated for Active subscriptions.")
        return redirect('subscriptions:subscription_detail', pk=subscription_pk)

    if not sub.lines.exists():
        messages.error(request, "Cannot generate invoice: Subscription has no line items.")
        return redirect('subscriptions:subscription_detail', pk=subscription_pk)

    invoice = generate_invoice(sub)
    if invoice:
        messages.success(request, f"Invoice {invoice.number} successfully created/retrieved for period {invoice.period_start} to {invoice.period_end}.")
        return redirect('billing:invoice_detail', pk=invoice.pk)
    else:
        messages.info(request, "Invoice for the current period has already been created.")
        return redirect('subscriptions:subscription_detail', pk=subscription_pk)


@staff_or_admin_required
def invoice_confirm_view(request, pk):
    if request.method != 'POST':
        return redirect('billing:invoice_detail', pk=pk)

    invoice = get_object_or_404(Invoice, pk=pk)
    if invoice.status == Invoice.STATUS_DRAFT:
        invoice.status = Invoice.STATUS_CONFIRMED
        invoice.save(update_fields=['status', 'updated_at'])
        messages.success(request, f"Invoice {invoice.number} marked as Confirmed.")
    else:
        messages.error(request, f"Only Draft invoices can be confirmed.")
    return redirect('billing:invoice_detail', pk=pk)


@staff_or_admin_required
def invoice_cancel_view(request, pk):
    if request.method != 'POST':
        return redirect('billing:invoice_detail', pk=pk)

    invoice = get_object_or_404(Invoice, pk=pk)
    if invoice.status in [Invoice.STATUS_DRAFT, Invoice.STATUS_CONFIRMED]:
        invoice.status = Invoice.STATUS_CANCELLED
        invoice.save(update_fields=['status', 'updated_at'])
        messages.warning(request, f"Invoice {invoice.number} has been Cancelled.")
    else:
        messages.error(request, "Paid or already cancelled invoices cannot be cancelled.")
    return redirect('billing:invoice_detail', pk=pk)


@staff_or_admin_required
def invoice_send_email_view(request, pk):
    if request.method != 'POST':
        return redirect('billing:invoice_detail', pk=pk)

    invoice = get_object_or_404(Invoice, pk=pk)
    recipient = invoice.customer.email
    subject = f"Invoice {invoice.number} from Brightloop Software"
    message_body = (
        f"Dear {invoice.customer.get_full_name() or invoice.customer.email},\n\n"
        f"Here is your billing statement from Brightloop Software:\n"
        f"Invoice Number: {invoice.number}\n"
        f"Subscription: {invoice.subscription.number}\n"
        f"Billing Period: {invoice.period_start} to {invoice.period_end}\n"
        f"Total Amount: ${invoice.total}\n"
        f"Outstanding Balance: ${invoice.outstanding_balance}\n"
        f"Due Date: {invoice.due_date}\n\n"
        f"Thank you for choosing Brightloop Software!\n"
    )

    send_mail(
        subject=subject,
        message=message_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        fail_silently=False,
    )

    messages.success(request, f"Invoice {invoice.number} sent to {recipient} (logged to console).")
    return redirect('billing:invoice_detail', pk=pk)


@login_required
def invoice_print_view(request, pk):
    # Security: customers can ONLY access their own invoices; return 404 for other IDs
    if request.user.role == 'customer':
        invoice = get_object_or_404(
            Invoice.objects.select_related('customer', 'subscription__plan')
            .prefetch_related('lines__product', 'lines__variant', 'lines__tax', 'payments'),
            pk=pk,
            customer=request.user
        )
    else:
        invoice = get_object_or_404(
            Invoice.objects.select_related('customer', 'subscription__plan')
            .prefetch_related('lines__product', 'lines__variant', 'lines__tax', 'payments'),
            pk=pk
        )

    return render(request, 'billing/invoice_print.html', {'invoice': invoice})


@login_required
def payment_create_view(request, invoice_pk):
    # Security: customers can ONLY pay their own invoices; return 404 for other IDs
    if request.user.role == 'customer':
        invoice = get_object_or_404(Invoice, pk=invoice_pk, customer=request.user)
    else:
        if not (request.user.role in ['admin', 'staff'] or request.user.is_superuser):
            raise PermissionDenied("Staff or admin privileges required.")
        invoice = get_object_or_404(Invoice, pk=invoice_pk)

    if invoice.status == Invoice.STATUS_CANCELLED:
        messages.error(request, "Cannot record payment on a cancelled invoice.")
        return redirect('billing:invoice_detail', pk=invoice_pk)

    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.invoice = invoice
            if payment.amount <= Decimal('0.00'):
                messages.error(request, "Payment amount must be greater than zero.")
                return redirect('billing:invoice_detail', pk=invoice_pk)

            payment.save()
            invoice.refresh_from_db()
            if invoice.status == Invoice.STATUS_PAID:
                messages.success(request, f"Payment of ${payment.amount} successful! Invoice {invoice.number} is now Paid in Full.")
            else:
                messages.success(request, f"Payment of ${payment.amount} received. Remaining balance: ${invoice.outstanding_balance}.")
        else:
            for err in form.errors.values():
                messages.error(request, err)

    return redirect('billing:invoice_detail', pk=invoice_pk)


@login_required
def customer_invoices_view(request):
    user = request.user
    today = timezone.now().date()

    all_invoices = Invoice.objects.filter(customer=user).select_related('subscription').prefetch_related('payments')

    # Summary metrics
    total_outstanding = sum(
        (inv.outstanding_balance for inv in all_invoices if inv.status != Invoice.STATUS_CANCELLED),
        Decimal('0.00')
    )
    total_paid = Payment.objects.filter(invoice__customer=user).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    overdue_count = all_invoices.filter(
        due_date__lt=today
    ).exclude(status__in=[Invoice.STATUS_PAID, Invoice.STATUS_CANCELLED]).count()

    # Status filter
    status_filter = request.GET.get('status', '').strip()
    invoices_queryset = all_invoices
    if status_filter:
        invoices_queryset = invoices_queryset.filter(status=status_filter)

    paginator = Paginator(invoices_queryset.order_by('-due_date', '-id'), 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'billing/customer_invoices.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'total_outstanding': total_outstanding,
        'total_paid': total_paid,
        'overdue_count': overdue_count,
        'today': today,
    })
