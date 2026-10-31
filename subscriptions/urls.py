from django.urls import path
from . import views

app_name = 'subscriptions'

urlpatterns = [
    # Subscriptions
    path('', views.subscription_list_view, name='subscription_list'),
    path('portal/', views.customer_portal_view, name='customer_portal'),
    path('browse-plans/', views.browse_plans_view, name='browse_plans'),
    path('create/', views.subscription_create_view, name='subscription_create'),
    path('<int:pk>/', views.subscription_detail_view, name='subscription_detail'),
    path('<int:pk>/transition/<str:target_status>/', views.subscription_transition_view, name='subscription_transition'),
    path('<int:pk>/lines/add/', views.subscription_line_add_view, name='subscription_line_add'),
    path('<int:pk>/lines/<int:line_pk>/delete/', views.subscription_line_delete_view, name='subscription_line_delete'),

    # Quotation Templates
    path('templates/', views.template_list_view, name='template_list'),
    path('templates/create/', views.template_create_view, name='template_create'),
    path('templates/<int:pk>/', views.template_detail_view, name='template_detail'),
]
