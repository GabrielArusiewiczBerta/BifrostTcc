from django.conf import settings
from django.db import models


class ApiKey(models.Model):
    """Chave de API por usuário. Só o hash é guardado; a chave em claro aparece uma única vez."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_key')
    key_hash = models.CharField(max_length=64, unique=True)
    prefix = models.CharField(max_length=12)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} ({self.prefix}...)"


class NetworkCredential(models.Model):
    """Credencial de acesso do usuário a uma rede blockchain, exibida no painel unificado (Wallet).

    Guarda apenas um rótulo e um identificador externo (ex.: endereço público) informados
    pelo próprio usuário; nenhuma chave privada é solicitada ou armazenada.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='network_credentials')
    blockchain = models.CharField(max_length=20)
    label = models.CharField(max_length=60)
    external_id = models.CharField(max_length=200, blank=True)
    connected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['blockchain', 'label']

    def __str__(self):
        return f"{self.user} · {self.blockchain} · {self.label}"


class RequestLog(models.Model):
    """Contabilização de requisições (web e API) por usuário."""
    SOURCES = [('web', 'Interface web'), ('api', 'API REST')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='request_logs')
    source = models.CharField(max_length=3, choices=SOURCES)
    endpoint = models.CharField(max_length=20)
    method = models.CharField(max_length=6)
    status_code = models.PositiveSmallIntegerField()
    blockchain = models.CharField(max_length=20, blank=True)
    tx_count = models.PositiveIntegerField(default=0)
    bytes_stored = models.PositiveBigIntegerField(default=0)
    fee_native = models.FloatField(default=0)
    cost_usd = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', '-created_at'])]

    def __str__(self):
        return f"{self.user} {self.source}:{self.endpoint} {self.status_code}"
