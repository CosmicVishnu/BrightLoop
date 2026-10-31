from django.urls import path
from . import views

app_name = 'catalog'

urlpatterns = [
    # Products & Variants
    path('products/', views.product_list_view, name='product_list'),
    path('products/create/', views.product_create_view, name='product_create'),
    path('products/<int:pk>/edit/', views.product_edit_view, name='product_edit'),
    path('variants/create/', views.variant_create_view, name='variant_create'),
    path('variants/<int:pk>/delete/', views.variant_delete_view, name='variant_delete'),

    # Plans
    path('plans/', views.plan_list_view, name='plan_list'),
    path('plans/create/', views.plan_create_view, name='plan_create'),
    path('plans/<int:pk>/edit/', views.plan_edit_view, name='plan_edit'),

    # Taxes (Admin Only)
    path('taxes/', views.tax_list_view, name='tax_list'),
    path('taxes/create/', views.tax_create_view, name='tax_create'),
    path('taxes/<int:pk>/edit/', views.tax_edit_view, name='tax_edit'),

    # Discounts (Admin Only)
    path('discounts/', views.discount_list_view, name='discount_list'),
    path('discounts/create/', views.discount_create_view, name='discount_create'),
    path('discounts/<int:pk>/edit/', views.discount_edit_view, name='discount_edit'),
]
