from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    path('', views.invoice_list_view, name='invoice_list'),
    path('my-invoices/', views.customer_invoices_view, name='customer_invoices'),
    path('<int:pk>/', views.invoice_detail_view, name='invoice_detail'),
    path('<int:pk>/confirm/', views.invoice_confirm_view, name='invoice_confirm'),
    path('<int:pk>/cancel/', views.invoice_cancel_view, name='invoice_cancel'),
    path('<int:pk>/send/', views.invoice_send_email_view, name='invoice_send_email'),
    path('<int:pk>/print/', views.invoice_print_view, name='invoice_print'),
    path('<int:invoice_pk>/pay/', views.payment_create_view, name='payment_create'),
    path('generate-subscription/<int:subscription_pk>/', views.generate_single_invoice_view, name='generate_single_invoice'),
]
