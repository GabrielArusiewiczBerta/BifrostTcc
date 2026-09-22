from django.contrib import admin

from .models import ApiKey, RequestLog


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ('user', 'prefix', 'created_at', 'last_used_at')
    readonly_fields = ('user', 'key_hash', 'prefix', 'created_at', 'last_used_at')


@admin.register(RequestLog)
class RequestLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'source', 'endpoint', 'blockchain', 'status_code', 'tx_count', 'cost_usd')
    list_filter = ('source', 'endpoint', 'blockchain', 'status_code')
    date_hierarchy = 'created_at'
