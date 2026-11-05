from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class ApiKey(models.Model):
    """Chave de API por usuário. Só o hash é guardado; a chave em claro aparece uma única vez."""
    VALIDITY = timedelta(hours=1)

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_key')
    key_hash = models.CharField(max_length=64, unique=True)
    prefix = models.CharField(max_length=12)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

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


class UserBlockchainKey(models.Model):
    """Chave de blockchain própria do usuário, opcional (rede real: Stellar/Bitcoin/Ethereum).

    Gerada pelo próprio NodeConnect a pedido do usuário (botão "Gerar chave própria" na
    Carteira). Guardada cifrada (bifrost_app/server_secrets.py); sem isso, as operações
    reais dessa blockchain usam a chave central compartilhada (core_bifrost/testnet_keys.py),
    que continua sendo o padrão. A troca entre uma e outra é feita por core_bifrost/user_keys.py.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='blockchain_keys')
    blockchain = models.CharField(max_length=20)
    public_address = models.CharField(max_length=200)
    encrypted_secret = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'blockchain'], name='unique_user_blockchain_key')]

    def __str__(self):
        return f"{self.user} · {self.blockchain} · {self.public_address}"


class Invoice(models.Model):
    """Fatura mensal simulada, com boleto fictício (trabalho acadêmico, sem valor fiscal real).

    Resume o custo (RequestLog.cost_usd) das operações pagas do usuário num mês/ano, convertido
    pra BRL por uma cotação de referência fixa (bifrost_app/invoicing.py, mesmo padrão das
    cotações fixas de core_bifrost/costs.py). Gerada por `manage.py gerar_faturas` (pensado pra
    rodar via cron todo início de mês) ou manualmente pelo botão no painel do administrador.
    """
    STATUS = [('pendente', 'Pendente'), ('pago', 'Pago (simulado)')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='invoices')
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    amount_brl = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    boleto_number = models.CharField(max_length=20)
    linha_digitavel = models.CharField(max_length=60)
    status = models.CharField(max_length=10, choices=STATUS, default='pendente')
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f"{self.user} · {self.month:02d}/{self.year} · R$ {self.amount_brl}"


class RequestLog(models.Model):
    """Contabilização de requisições (web e API) por usuário."""
    SOURCES = [('web', 'Interface web'), ('api', 'API REST')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='request_logs')
    source = models.CharField(max_length=3, choices=SOURCES)
    endpoint = models.CharField(max_length=20)
    method = models.CharField(max_length=6)
    status_code = models.PositiveSmallIntegerField()
    blockchain = models.CharField(max_length=20, blank=True)
    tx_hash = models.CharField(max_length=80, blank=True, help_text='Hash do primeiro fragmento gravado/migrado, se a operação gerou algum.')
    tx_count = models.PositiveIntegerField(default=0)
    bytes_stored = models.PositiveBigIntegerField(default=0)
    fee_native = models.FloatField(default=0)
    cost_usd = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    invoice = models.ForeignKey(
        'Invoice', null=True, blank=True, on_delete=models.SET_NULL, related_name='items',
        help_text='Preenchido quando o custo desta operação já entrou em alguma fatura (evita cobrar de novo).',
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', '-created_at'])]

    def __str__(self):
        return f"{self.user} {self.source}:{self.endpoint} {self.status_code}"
