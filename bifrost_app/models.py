from django.db import models

class NodeStatus(models.Model):
    name = models.CharField(max_length=100, unique=True)
    blockchain_code = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    block_height = models.IntegerField(default=102450)
    latency_ms = models.IntegerField(default=45)
    last_sync = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.blockchain_code})"

class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('STORE', 'Armazenar Dados'),
        ('RETRIEVE', 'Recuperar Dados'),
        ('MIGRATE', 'Migrar Transação'),
    ]
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    blockchain = models.CharField(max_length=50)
    transaction_hash = models.CharField(max_length=255)
    details = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.action_type}] {self.blockchain} - {self.transaction_hash[:12]}"
