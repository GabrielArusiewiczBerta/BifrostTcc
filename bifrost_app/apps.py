from django.apps import AppConfig


class BifrostAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bifrost_app'
    verbose_name = 'Bifröst Blockchain Interoperability'

    def ready(self):
        # Registra em core_bifrost (que não conhece Django) como achar a chave de
        # blockchain própria de um usuário, se ele tiver cadastrado uma na Carteira.
        from core_bifrost.user_keys import register_resolver
        from .server_secrets import decrypt_secret

        def resolver(owner_pk, blockchain_code):
            from .models import UserBlockchainKey
            rec = UserBlockchainKey.objects.filter(user_id=owner_pk, blockchain=blockchain_code).first()
            return decrypt_secret(rec.encrypted_secret) if rec else None

        register_resolver(resolver)
