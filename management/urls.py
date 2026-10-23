from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('sales/', views.sales_view, name='sales'),
    path('sales/<int:sale_id>/cancel/', views.cancel_sale_view, name='cancel_sale'),
    path('api/price-preview/', views.price_preview_api, name='price_preview_api'),
    path('deliveries/', views.deliveries_view, name='deliveries'),
    path('expenses/', views.expenses_view, name='expenses'),
    path('inventory/', views.inventory_view, name='inventory'),
    path('transactions/', views.transactions_view, name='transactions'),
    path('transactions/export/', views.export_transactions_csv, name='export_transactions_csv'),
    path('reports/', views.reports_view, name='reports'),
    path('settings/', views.settings_view, name='settings'),
]
