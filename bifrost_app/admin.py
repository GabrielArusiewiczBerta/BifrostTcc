from django.contrib import admin

from .models import ApiKey, Invoice, NetworkCredential, RequestLog, UserBlockchainKey


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ('user', 'prefix', 'created_at', 'last_used_at')
    readonly_fields = ('user', 'key_hash', 'prefix', 'created_at', 'last_used_at')


@admin.register(NetworkCredential)
class NetworkCredentialAdmin(admin.ModelAdmin):
    list_display = ('user', 'blockchain', 'label', 'external_id', 'connected_at')
    list_filter = ('blockchain',)


@admin.register(UserBlockchainKey)
class UserBlockchainKeyAdmin(admin.ModelAdmin):
    list_display = ('user', 'blockchain', 'public_address', 'created_at')
    list_filter = ('blockchain',)
    readonly_fields = ('user', 'blockchain', 'public_address', 'encrypted_secret', 'created_at')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('user', 'month', 'year', 'amount_brl', 'due_date', 'status')
    list_filter = ('status', 'year', 'month')


@admin.register(RequestLog)
class RequestLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'source', 'endpoint', 'blockchain', 'status_code', 'tx_count', 'cost_usd')
    list_filter = ('source', 'endpoint', 'blockchain', 'status_code')
    date_hierarchy = 'created_at'
