from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register_view, name='register'),
    path('account/', views.account_view, name='account'),
    path('custo/gravar/', views.preview_store_cost, name='preview_store_cost'),
    path('store/iniciar/', views.store_start_view, name='store_start'),
    path('store/passo/', views.store_step_view, name='store_step'),
    path('custo/migrar/', views.preview_migrate_cost, name='preview_migrate_cost'),
    path('migrate/iniciar/', views.migrate_start_view, name='migrate_start'),
    path('migrate/passo/', views.migrate_step_view, name='migrate_step'),
    path('painel-admin/', views.admin_accounting_view, name='admin_accounting'),
    path('account/api-key/', views.generate_api_key_view, name='generate_api_key'),
    path('account/api-key/revogar/', views.revoke_api_key_view, name='revoke_api_key'),

    path('', views.dashboard_view, name='dashboard'),
    path('store/', views.store_view, name='store'),
    path('retrieve/', views.retrieve_view, name='retrieve'),
    path('migrate/', views.migrate_view, name='migrate'),
    path('explorer/', views.explorer_view, name='explorer'),
    path('carteira/', views.wallet_view, name='wallet'),
    path('carteira/<int:pk>/renomear/', views.wallet_credential_rename, name='wallet_credential_rename'),
    path('carteira/<int:pk>/remover/', views.wallet_credential_delete, name='wallet_credential_delete'),
    path('consumo/', views.billing_view, name='billing'),

    # REST API endpoints
    path('api/store/', views.api_store, name='api_store'),
    path('api/retrieve/', views.api_retrieve, name='api_retrieve'),
    path('api/migrate/', views.api_migrate, name='api_migrate'),
    path('api/transactions/', views.api_transactions, name='api_transactions'),
    path('api/estimate/', views.api_estimate, name='api_estimate'),
]
