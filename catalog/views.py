from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from accounts.decorators import admin_required, staff_or_admin_required
from .models import Product, Variant, Plan, Tax, Discount
from .forms import ProductForm, VariantForm, PlanForm, TaxForm, DiscountForm

# Products & Variants
@staff_or_admin_required
def product_list_view(request):
    products = Product.objects.prefetch_related('variants').all()
    variant_form = VariantForm()
    return render(request, 'catalog/product_list.html', {
        'products': products,
        'variant_form': variant_form
    })

@staff_or_admin_required
def product_create_view(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            messages.success(request, f"Product '{product.name}' created.")
            return redirect('catalog:product_list')
    else:
        form = ProductForm()
    return render(request, 'catalog/product_form.html', {'form': form, 'title': 'Create Product'})

@staff_or_admin_required
def product_edit_view(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"Product '{product.name}' updated.")
            return redirect('catalog:product_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'catalog/product_form.html', {'form': form, 'product': product, 'title': f'Edit Product: {product.name}'})

@staff_or_admin_required
def variant_create_view(request):
    if request.method == 'POST':
        form = VariantForm(request.POST)
        if form.is_valid():
            variant = form.save()
            messages.success(request, f"Variant '{variant}' added.")
        else:
            for error in form.errors.values():
                messages.error(request, error)
    return redirect('catalog:product_list')

@staff_or_admin_required
def variant_delete_view(request, pk):
    variant = get_object_or_404(Variant, pk=pk)
    if request.method == 'POST':
        name = str(variant)
        variant.delete()
        messages.info(request, f"Variant '{name}' removed.")
    return redirect('catalog:product_list')


# Plans
@staff_or_admin_required
def plan_list_view(request):
    plans = Plan.objects.all()
    return render(request, 'catalog/plan_list.html', {'plans': plans})

@staff_or_admin_required
def plan_create_view(request):
    if request.method == 'POST':
        form = PlanForm(request.POST)
        if form.is_valid():
            plan = form.save()
            messages.success(request, f"Plan '{plan.name}' created.")
            return redirect('catalog:plan_list')
    else:
        form = PlanForm()
    return render(request, 'catalog/plan_form.html', {'form': form, 'title': 'Create Plan'})

@staff_or_admin_required
def plan_edit_view(request, pk):
    plan = get_object_or_404(Plan, pk=pk)
    if request.method == 'POST':
        form = PlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, f"Plan '{plan.name}' updated.")
            return redirect('catalog:plan_list')
    else:
        form = PlanForm(instance=plan)
    return render(request, 'catalog/plan_form.html', {'form': form, 'plan': plan, 'title': f'Edit Plan: {plan.name}'})


# Taxes (Admin Only)
@admin_required
def tax_list_view(request):
    taxes = Tax.objects.all()
    return render(request, 'catalog/tax_list.html', {'taxes': taxes})

@admin_required
def tax_create_view(request):
    if request.method == 'POST':
        form = TaxForm(request.POST)
        if form.is_valid():
            tax = form.save()
            messages.success(request, f"Tax '{tax.name}' created.")
            return redirect('catalog:tax_list')
    else:
        form = TaxForm()
    return render(request, 'catalog/tax_form.html', {'form': form, 'title': 'Create Tax'})

@admin_required
def tax_edit_view(request, pk):
    tax = get_object_or_404(Tax, pk=pk)
    if request.method == 'POST':
        form = TaxForm(request.POST, instance=tax)
        if form.is_valid():
            form.save()
            messages.success(request, f"Tax '{tax.name}' updated.")
            return redirect('catalog:tax_list')
    else:
        form = TaxForm(instance=tax)
    return render(request, 'catalog/tax_form.html', {'form': form, 'tax': tax, 'title': f'Edit Tax: {tax.name}'})


# Discounts (Admin Only)
@admin_required
def discount_list_view(request):
    discounts = Discount.objects.prefetch_related('products').all()
    return render(request, 'catalog/discount_list.html', {'discounts': discounts})

@admin_required
def discount_create_view(request):
    if request.method == 'POST':
        form = DiscountForm(request.POST)
        if form.is_valid():
            discount = form.save()
            messages.success(request, f"Discount '{discount.name}' created.")
            return redirect('catalog:discount_list')
    else:
        form = DiscountForm()
    return render(request, 'catalog/discount_form.html', {'form': form, 'title': 'Create Discount'})

@admin_required
def discount_edit_view(request, pk):
    discount = get_object_or_404(Discount, pk=pk)
    if request.method == 'POST':
        form = DiscountForm(request.POST, instance=discount)
        if form.is_valid():
            form.save()
            messages.success(request, f"Discount '{discount.name}' updated.")
            return redirect('catalog:discount_list')
    else:
        form = DiscountForm(instance=discount)
    return render(request, 'catalog/discount_form.html', {'form': form, 'discount': discount, 'title': f'Edit Discount: {discount.name}'})
