from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from accounts.decorators import staff_or_admin_required
from .models import QuotationTemplate, QuotationTemplateLine, Subscription, SubscriptionLine
from .forms import QuotationTemplateForm, QuotationTemplateLineForm, SubscriptionCreateForm, SubscriptionLineForm
from catalog.models import Plan, Product, Tax

@staff_or_admin_required
def subscription_list_view(request):
    status_filter = request.GET.get('status', '')
    query = request.GET.get('q', '')

    queryset = Subscription.objects.select_related('customer', 'plan').prefetch_related('lines').all()

    if status_filter:
        queryset = queryset.filter(status=status_filter)
    if query:
        queryset = queryset.filter(customer__email__icontains=query) | queryset.filter(number__icontains=query)

    paginator = Paginator(queryset, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Check auto-close on displayed active subscriptions
    for sub in page_obj:
        if sub.status in [Subscription.STATUS_ACTIVE, Subscription.STATUS_PAUSED]:
            sub.check_and_auto_close()

    return render(request, 'subscriptions/subscription_list.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'query': query,
    })


@staff_or_admin_required
def subscription_create_view(request):
    if request.method == 'POST':
        form = SubscriptionCreateForm(request.POST)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.status = Subscription.STATUS_DRAFT
            sub.save()

            # If template selected, copy lines
            if sub.template:
                default_tax = Tax.objects.filter(is_active=True).first()
                for tline in sub.template.lines.all():
                    SubscriptionLine.objects.create(
                        subscription=sub,
                        product=tline.product,
                        quantity=tline.quantity,
                        unit_price=tline.product.sales_price,
                        tax=default_tax
                    )

            messages.success(request, f"Subscription {sub.number} created as Draft.")
            return redirect('subscriptions:subscription_detail', pk=sub.pk)
    else:
        form = SubscriptionCreateForm()

    return render(request, 'subscriptions/subscription_create.html', {'form': form})


@login_required
def subscription_detail_view(request, pk):
    # Security: customers can ONLY access their own subscriptions; return 404 for other IDs
    if request.user.role == 'customer':
        sub = get_object_or_404(
            Subscription.objects.select_related('customer', 'plan', 'template')
            .prefetch_related('lines__product', 'lines__variant', 'lines__tax', 'invoices'),
            pk=pk,
            customer=request.user
        )
    else:
        sub = get_object_or_404(
            Subscription.objects.select_related('customer', 'plan', 'template')
            .prefetch_related('lines__product', 'lines__variant', 'lines__tax', 'invoices'),
            pk=pk
        )

    # Trigger auto-close check
    sub.check_and_auto_close()

    line_form = SubscriptionLineForm() if (sub.status in [Subscription.STATUS_DRAFT, Subscription.STATUS_QUOTATION] and request.user.role != 'customer') else None

    # Available transitions
    is_customer = request.user.role == 'customer'
    available_transitions = []

    if is_customer:
        # Show Pause / Close / Renew buttons only when the plan's pausable / closable / renewable flags allow it
        if sub.status == Subscription.STATUS_ACTIVE and sub.plan.pausable and sub.can_transition_to(Subscription.STATUS_PAUSED):
            available_transitions.append({
                'action': Subscription.STATUS_PAUSED,
                'label': 'Pause Subscription',
                'btn': 'warning',
                'confirm': f"Are you sure you want to pause subscription {sub.number}? Your recurring services will be temporarily suspended."
            })
        if sub.status == Subscription.STATUS_PAUSED and sub.plan.pausable and sub.can_transition_to(Subscription.STATUS_ACTIVE):
            available_transitions.append({
                'action': Subscription.STATUS_ACTIVE,
                'label': 'Resume Subscription',
                'btn': 'success',
                'confirm': f"Are you sure you want to resume subscription {sub.number}?"
            })
        if sub.status in [Subscription.STATUS_ACTIVE, Subscription.STATUS_PAUSED] and sub.plan.closable and sub.can_transition_to(Subscription.STATUS_CLOSED):
            available_transitions.append({
                'action': Subscription.STATUS_CLOSED,
                'label': 'Close Subscription',
                'btn': 'danger',
                'confirm': f"Are you sure you want to close subscription {sub.number}? Services will be terminated according to plan terms."
            })
        if sub.status == Subscription.STATUS_CLOSED and sub.plan.renewable and sub.can_transition_to(Subscription.STATUS_ACTIVE):
            available_transitions.append({
                'action': Subscription.STATUS_ACTIVE,
                'label': 'Renew Subscription',
                'btn': 'success',
                'confirm': f"Are you sure you want to renew and reactivate subscription {sub.number}?"
            })
    else:
        # Admin / Staff transitions
        if sub.can_transition_to(Subscription.STATUS_QUOTATION):
            available_transitions.append({'action': Subscription.STATUS_QUOTATION, 'label': 'Convert to Quotation', 'btn': 'primary', 'confirm': None})
        if sub.can_transition_to(Subscription.STATUS_CONFIRMED):
            available_transitions.append({'action': Subscription.STATUS_CONFIRMED, 'label': 'Confirm Subscription', 'btn': 'success', 'confirm': None})
        if sub.can_transition_to(Subscription.STATUS_ACTIVE):
            label = 'Renew / Reactivate' if sub.status == Subscription.STATUS_CLOSED else ('Resume' if sub.status == Subscription.STATUS_PAUSED else 'Activate Subscription')
            available_transitions.append({'action': Subscription.STATUS_ACTIVE, 'label': label, 'btn': 'success', 'confirm': None})
        if sub.can_transition_to(Subscription.STATUS_PAUSED):
            available_transitions.append({'action': Subscription.STATUS_PAUSED, 'label': 'Pause Subscription', 'btn': 'warning', 'confirm': None})
        if sub.can_transition_to(Subscription.STATUS_CLOSED):
            available_transitions.append({'action': Subscription.STATUS_CLOSED, 'label': 'Close Subscription', 'btn': 'danger', 'confirm': None})

    context = {
        'subscription': sub,
        'lines': sub.lines.all(),
        'line_form': line_form,
        'available_transitions': available_transitions,
        'is_customer': is_customer,
    }
    return render(request, 'subscriptions/subscription_detail.html', context)


@login_required
def subscription_transition_view(request, pk, target_status):
    if request.method != 'POST':
        return redirect('subscriptions:subscription_detail', pk=pk)

    # Security: customers can only access their own subscriptions; return 404 for other IDs
    if request.user.role == 'customer':
        sub = get_object_or_404(Subscription, pk=pk, customer=request.user)
        # Customer can only trigger Pause, Close, Renew when plan flags permit
        allowed = []
        if sub.status == Subscription.STATUS_ACTIVE and sub.plan.pausable:
            allowed.append(Subscription.STATUS_PAUSED)
        if sub.status == Subscription.STATUS_PAUSED and sub.plan.pausable:
            allowed.append(Subscription.STATUS_ACTIVE)
        if sub.status in [Subscription.STATUS_ACTIVE, Subscription.STATUS_PAUSED] and sub.plan.closable:
            allowed.append(Subscription.STATUS_CLOSED)
        if sub.status == Subscription.STATUS_CLOSED and sub.plan.renewable:
            allowed.append(Subscription.STATUS_ACTIVE)

        if target_status not in allowed:
            messages.error(request, f"Action '{target_status}' is not permitted for this subscription.")
            return redirect('subscriptions:subscription_detail', pk=pk)
    else:
        if not (request.user.role in ['admin', 'staff'] or request.user.is_superuser):
            raise PermissionDenied("Staff or admin privileges required.")
        sub = get_object_or_404(Subscription, pk=pk)

    if not sub.can_transition_to(target_status):
        messages.error(
            request,
            f"Invalid transition: Cannot change subscription from '{sub.status}' to '{target_status}'. Transition rejected."
        )
        return redirect('subscriptions:subscription_detail', pk=pk)

    old_status = sub.status
    sub.status = target_status

    if target_status == Subscription.STATUS_ACTIVE and not sub.next_billing_date:
        sub.next_billing_date = sub.start_date or timezone.now().date()

    sub.save(update_fields=['status', 'next_billing_date', 'updated_at'])
    messages.success(request, f"Subscription {sub.number} transitioned from {old_status} to {target_status}.")
    return redirect('subscriptions:subscription_detail', pk=pk)


@staff_or_admin_required
def subscription_line_add_view(request, pk):
    sub = get_object_or_404(Subscription, pk=pk)
    if sub.status not in [Subscription.STATUS_DRAFT, Subscription.STATUS_QUOTATION]:
        messages.error(request, "Lines can only be added to Draft or Quotation subscriptions.")
        return redirect('subscriptions:subscription_detail', pk=pk)

    if request.method == 'POST':
        form = SubscriptionLineForm(request.POST)
        if form.is_valid():
            line = form.save(commit=False)
            line.subscription = sub
            if line.variant:
                line.unit_price = line.variant.total_unit_price
            elif not line.unit_price:
                line.unit_price = line.product.sales_price
            line.save()
            messages.success(request, f"Added line: {line.product.name}")
        else:
            for err in form.errors.values():
                messages.error(request, err)
    return redirect('subscriptions:subscription_detail', pk=pk)


@staff_or_admin_required
def subscription_line_delete_view(request, pk, line_pk):
    sub = get_object_or_404(Subscription, pk=pk)
    if sub.status not in [Subscription.STATUS_DRAFT, Subscription.STATUS_QUOTATION]:
        messages.error(request, "Lines can only be removed from Draft or Quotation subscriptions.")
        return redirect('subscriptions:subscription_detail', pk=pk)

    line = get_object_or_404(SubscriptionLine, pk=line_pk, subscription=sub)
    if request.method == 'POST':
        line.delete()
        messages.info(request, "Line removed.")
    return redirect('subscriptions:subscription_detail', pk=pk)


# Quotation Templates
@staff_or_admin_required
def template_list_view(request):
    templates = QuotationTemplate.objects.prefetch_related('lines__product').all()
    return render(request, 'subscriptions/template_list.html', {'templates': templates})


@staff_or_admin_required
def template_create_view(request):
    if request.method == 'POST':
        form = QuotationTemplateForm(request.POST)
        if form.is_valid():
            tmpl = form.save()
            messages.success(request, f"Quotation template '{tmpl.name}' created.")
            return redirect('subscriptions:template_detail', pk=tmpl.pk)
    else:
        form = QuotationTemplateForm()
    return render(request, 'subscriptions/template_form.html', {'form': form, 'title': 'Create Quotation Template'})


@staff_or_admin_required
def template_detail_view(request, pk):
    tmpl = get_object_or_404(QuotationTemplate.objects.prefetch_related('lines__product'), pk=pk)
    if request.method == 'POST':
        line_form = QuotationTemplateLineForm(request.POST)
        if line_form.is_valid():
            line = line_form.save(commit=False)
            line.template = tmpl
            line.save()
            messages.success(request, f"Added product to template.")
            return redirect('subscriptions:template_detail', pk=pk)
    else:
        line_form = QuotationTemplateLineForm()

    return render(request, 'subscriptions/template_detail.html', {'template': tmpl, 'line_form': line_form})


# Customer Portal - My Subscriptions
@login_required
def customer_portal_view(request):
    user = request.user
    subs = Subscription.objects.filter(customer=user).select_related('plan').prefetch_related('lines', 'invoices')

    # Trigger auto-close check for active/paused subscriptions
    for sub in subs.filter(status__in=[Subscription.STATUS_ACTIVE, Subscription.STATUS_PAUSED]):
        sub.check_and_auto_close()

    total_subs_count = subs.count()
    active_subs_count = subs.filter(status=Subscription.STATUS_ACTIVE).count()
    quotation_count = subs.filter(status=Subscription.STATUS_QUOTATION).count()

    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        subs = subs.filter(status=status_filter)

    paginator = Paginator(subs.order_by('-id'), 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'subscriptions/customer_portal.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'total_subs_count': total_subs_count,
        'active_subs_count': active_subs_count,
        'quotation_count': quotation_count,
    })


# Customer Portal - Browse Plans
@login_required
def browse_plans_view(request):
    today = timezone.now().date()
    plans = Plan.objects.all().prefetch_related('quotation_templates__lines__product')

    if request.method == 'POST':
        plan_id = request.POST.get('plan_id')
        plan = get_object_or_404(Plan, pk=plan_id)

        try:
            quantity = int(request.POST.get('quantity', 1))
        except (ValueError, TypeError):
            quantity = 1

        if quantity < plan.min_quantity:
            messages.error(request, f"Minimum quantity for plan '{plan.name}' is {plan.min_quantity}.")
            return redirect('subscriptions:browse_plans')

        payment_terms = request.POST.get('payment_terms', 'Immediate')
        notes = request.POST.get('notes', '').strip()

        # Create subscription in Quotation status
        sub = Subscription.objects.create(
            customer=request.user,
            plan=plan,
            start_date=today,
            payment_terms=payment_terms,
            status=Subscription.STATUS_QUOTATION,
            notes=notes
        )

        default_tax = Tax.objects.filter(is_active=True).first()

        # If plan has quotation template, copy lines scaled by quantity
        tmpl = plan.quotation_templates.first()
        if tmpl and tmpl.lines.exists():
            sub.template = tmpl
            sub.save(update_fields=['template'])
            for tline in tmpl.lines.all():
                SubscriptionLine.objects.create(
                    subscription=sub,
                    product=tline.product,
                    quantity=tline.quantity * quantity,
                    unit_price=tline.product.sales_price,
                    tax=default_tax
                )
        else:
            # Fallback to primary product at plan price
            default_prod = Product.objects.filter(is_active=True).first()
            if default_prod:
                SubscriptionLine.objects.create(
                    subscription=sub,
                    product=default_prod,
                    quantity=quantity,
                    unit_price=plan.price,
                    tax=default_tax
                )

        messages.success(
            request,
            f"Quotation {sub.number} for plan '{plan.name}' has been created! Our team will review and confirm your order."
        )
        return redirect('subscriptions:subscription_detail', pk=sub.pk)

    return render(request, 'subscriptions/browse_plans.html', {'plans': plans, 'today': today})
