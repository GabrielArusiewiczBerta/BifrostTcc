from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('store/', views.store_view, name='store'),
    path('retrieve/', views.retrieve_view, name='retrieve'),
    path('migrate/', views.migrate_view, name='migrate'),
    path('explorer/', views.explorer_view, name='explorer'),
    
    # REST API endpoints
    path('api/store/', views.api_store, name='api_store'),
    path('api/retrieve/', views.api_retrieve, name='api_retrieve'),
    path('api/migrate/', views.api_migrate, name='api_migrate'),
    path('api/transactions/', views.api_transactions, name='api_transactions'),
]
