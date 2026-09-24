import datetime
import json
import os
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, Client
from django.utils import timezone

import core_bifrost.api as api
import core_bifrost.costs as costs
from cryptography.fernet import Fernet
from bifrost_app.models import ApiKey, NetworkCredential, RequestLog
import core_bifrost.db_manager as db
from core_bifrost.adapters.base_adapter import split_by_bytes
from core_bifrost.blockchain import Blockchain
from core_bifrost.custom_errors import (
    BlockchainNotFoundError, DecryptionError, TransactionNotFoundError, TransactionSizeError,
)


class LedgerMixin:
    """Cada teste usa um ledger SQLite temporário."""

    def setUp(self):
        fd, path = tempfile.mkstemp(suffix='.sqlite3')
        os.close(fd)
        self.addCleanup(os.remove, path)
        patcher = mock.patch.object(db, 'DB_PATH', path)
        patcher.start()
        self.addCleanup(patcher.stop)
        db.setup_database()


class ApiTests(LedgerMixin, SimpleTestCase):
    def test_store_retrieve_plain(self):
        hashes = api.store('olá mundo', 'RBB')
        res = api.retrieve(hashes[0])
        self.assertEqual(res['payload'], 'olá mundo')
        self.assertFalse(res['encrypted'])

    def test_encrypted_roundtrip_and_wrong_password(self):
        hashes = api.store('segredo', 'RBB', pw='senha123')
        self.assertEqual(api.retrieve(hashes[0], pw='senha123')['payload'], 'segredo')
        with self.assertRaises(DecryptionError):
            api.retrieve(hashes[0], pw='errada')
        raw = api.retrieve(hashes[0])
        self.assertTrue(raw['encrypted'])
        self.assertNotEqual(raw['payload'], 'segredo')

    def test_fragmentation_respects_byte_limit_and_order(self):
        text = 'ação ' * 30
        hashes = api.store(text, 'STELLAR', multiple_tx=True)
        self.assertGreater(len(hashes), 1)
        # recuperar a partir de um fragmento do meio devolve o texto na ordem original
        self.assertEqual(api.retrieve(hashes[len(hashes) // 2])['payload'], text)
        self.assertEqual(api.retrieve(hashes[-1])['linked_hashes'], hashes)

    def test_size_error_without_multiple_tx(self):
        with self.assertRaises(TransactionSizeError):
            api.store('x' * 100, 'STELLAR')

    def test_encrypted_fragmented_roundtrip(self):
        hashes = api.store('conteúdo secreto e longo ' * 5, 'BITCOIN', pw='pw', multiple_tx=True)
        self.assertEqual(api.retrieve(hashes[2], pw='pw')['payload'], 'conteúdo secreto e longo ' * 5)

    def test_migrate_keeps_encrypted_data_readable(self):
        src = api.store('dado cifrado migrado', 'RBB', pw='abc')
        res = api.migrate(src[0], 'ETHEREUM')
        self.assertTrue(res['encrypted'])
        self.assertEqual(api.retrieve(res['new_hashes'][0], pw='abc')['payload'], 'dado cifrado migrado')
        with self.assertRaises(DecryptionError):
            api.retrieve(res['new_hashes'][0], pw='outra')

    def test_migrate_plain_with_fragmentation(self):
        src = api.store('a' * 200, 'RBB')
        res = api.migrate(src[0], 'STELLAR', multiple_tx=True)
        self.assertGreater(len(res['new_hashes']), 1)
        self.assertEqual(api.retrieve(res['new_hashes'][0])['payload'], 'a' * 200)

    def test_redundancy_creates_postgres_copy(self):
        hashes = api.store('espelho', 'RBB', redundancy=True)
        self.assertEqual(len(hashes), 2)
        self.assertEqual(api.retrieve(hashes[1])['blockchain'], 'POSTGRES')

    def test_unknown_hash_is_error_not_placeholder(self):
        with self.assertRaises(TransactionNotFoundError):
            api.retrieve('inexistente')

    def test_missing_chain_data_raises(self):
        hashes = api.store('x', 'RBB')
        with db.get_connection() as conn:
            conn.execute('DELETE FROM sim_storage')
        with self.assertRaises(TransactionNotFoundError):
            api.retrieve(hashes[0])

    def test_unsupported_chain(self):
        with self.assertRaises(BlockchainNotFoundError):
            api.store('x', Blockchain.HYPERLEDGER)

    def test_empty_payload_rejected(self):
        with self.assertRaises(ValueError):
            api.store('', 'RBB')

    def test_preview_does_not_leak_encrypted_plaintext(self):
        api.store('texto sigiloso', 'RBB', pw='pw')
        self.assertEqual(db.get_all_transactions()[0]['payload_preview'], '[criptografado]')


    def test_owner_isolation(self):
        h = api.store('privado', 'RBB', owner=1)[0]
        self.assertEqual(api.retrieve(h, owner=1)['payload'], 'privado')
        with self.assertRaises(TransactionNotFoundError):
            api.retrieve(h, owner=2)
        with self.assertRaises(TransactionNotFoundError):
            api.migrate(h, 'ETHEREUM', owner=2)
        self.assertEqual(len(db.get_all_transactions(owner=1)), 1)
        self.assertEqual(db.get_all_transactions(owner=2), [])


class SplitTests(SimpleTestCase):
    def test_never_splits_a_character_and_respects_limit(self):
        chunks = split_by_bytes('ééééé', 3)
        self.assertEqual(chunks, ['é', 'é', 'é', 'é', 'é'])
        self.assertTrue(all(len(c.encode()) <= 3 for c in chunks))
        self.assertEqual(''.join(chunks), 'ééééé')


class RestApiTests(LedgerMixin, TestCase):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.user = User.objects.create_user('ana', password='Senha-forte-123')
        self.other = User.objects.create_user('beto', password='Senha-forte-123')
        self.key = self.make_key(self.client, self.user)
        self.other_key = self.make_key(Client(), self.other)

    def make_key(self, client, user):
        client.force_login(user)
        r = client.post('/account/api-key/')
        return r.context['new_api_key']

    def api(self, method, url, body=None, key=None, **extra):
        headers = {'HTTP_AUTHORIZATION': f'Bearer {key or self.key}'}
        headers.update(extra)
        c = Client()
        if method == 'get':
            return c.get(url, body or {}, **headers)
        return c.post(url, data=json.dumps(body or {}), content_type='application/json', **headers)

    def test_api_requires_valid_key(self):
        c = Client()
        self.assertEqual(c.get('/api/transactions/').status_code, 401)
        self.assertEqual(c.get('/api/transactions/', HTTP_AUTHORIZATION='Bearer errada').status_code, 401)
        self.assertEqual(c.post('/api/store/', data='{}', content_type='application/json').status_code, 401)

    def test_key_is_stored_hashed(self):
        stored = ApiKey.objects.get(user=self.user)
        self.assertNotEqual(stored.key_hash, self.key)
        self.assertEqual(len(stored.key_hash), 64)
        self.assertTrue(self.key.startswith(stored.prefix))

    def test_regenerating_key_revokes_old_one(self):
        c = Client()
        c.force_login(self.user)
        new_key = c.post('/account/api-key/').context['new_api_key']
        self.assertEqual(self.api('get', '/api/transactions/', key=self.key).status_code, 401)
        self.assertEqual(self.api('get', '/api/transactions/', key=new_key).status_code, 200)

    def test_store_and_retrieve_with_password_header(self):
        r = self.api('post', '/api/store/', {'payload': 'oi', 'blockchain': 'RBB', 'password': 'pw'})
        self.assertEqual(r.status_code, 200)
        h = r.json()['hashes'][0]
        ok = self.api('get', '/api/retrieve/', {'hash': h}, HTTP_X_BIFROST_PASSWORD='pw')
        self.assertEqual(ok.json()['data']['payload'], 'oi')
        bad = self.api('get', '/api/retrieve/', {'hash': h}, HTTP_X_BIFROST_PASSWORD='x')
        self.assertEqual(bad.status_code, 403)

    def test_password_in_query_string_is_ignored(self):
        h = self.api('post', '/api/store/', {'payload': 'oi', 'blockchain': 'RBB', 'password': 'pw'}).json()['hashes'][0]
        res = self.api('get', '/api/retrieve/', {'hash': h, 'password': 'pw'}).json()
        self.assertNotEqual(res['data']['payload'], 'oi')

    def test_users_cannot_see_each_others_data(self):
        h = self.api('post', '/api/store/', {'payload': 'da ana', 'blockchain': 'RBB'}).json()['hashes'][0]
        self.assertEqual(self.api('get', '/api/retrieve/', {'hash': h}, key=self.other_key).status_code, 404)
        self.assertEqual(self.api('get', '/api/transactions/', key=self.other_key).json()['count'], 0)
        self.assertEqual(self.api('get', '/api/transactions/').json()['count'], 1)

    def test_transactions_do_not_expose_salt_or_key(self):
        self.api('post', '/api/store/', {'payload': 'oi', 'blockchain': 'RBB', 'password': 'pw'})
        tx = self.api('get', '/api/transactions/').json()['transactions'][0]
        self.assertNotIn('salt', tx)
        self.assertNotIn('key', tx)
        self.assertNotIn('owner', tx)
        self.assertTrue(tx['encrypted'])

    def test_error_statuses(self):
        self.assertEqual(self.api('get', '/api/retrieve/', {'hash': 'nao-existe'}).status_code, 404)
        self.assertEqual(self.api('get', '/api/retrieve/').status_code, 400)
        self.assertEqual(self.api('post', '/api/store/', {'payload': '', 'blockchain': 'RBB'}).status_code, 400)
        self.assertEqual(self.api('post', '/api/store/', {'payload': 'x', 'blockchain': 'XYZ'}).status_code, 400)
        self.assertEqual(self.api('get', '/api/store/').status_code, 405)
        r = Client().post('/api/store/', data='não é json', content_type='application/json',
                          HTTP_AUTHORIZATION=f'Bearer {self.key}')
        self.assertEqual(r.status_code, 400)

    def test_requests_are_accounted(self):
        self.api('post', '/api/store/', {'payload': 'x', 'blockchain': 'STELLAR'})
        self.api('get', '/api/retrieve/', {'hash': 'nao-existe'})
        logs = RequestLog.objects.filter(user=self.user, source='api')
        self.assertEqual(logs.count(), 2)
        self.assertEqual(logs.get(endpoint='store').blockchain, 'STELLAR')
        self.assertEqual(logs.get(endpoint='retrieve').status_code, 404)
        self.assertEqual(RequestLog.objects.filter(user=self.other).count(), 0)

    def test_web_requires_login_and_accounts_usage(self):
        anon = Client()
        for path in ('/', '/store/', '/retrieve/', '/migrate/', '/explorer/', '/account/'):
            r = anon.get(path)
            self.assertEqual(r.status_code, 302, path)
            self.assertIn('/login/', r['Location'])
        self.client.force_login(self.user)
        for path in ('/', '/store/', '/retrieve/', '/migrate/', '/explorer/', '/account/'):
            self.assertEqual(self.client.get(path).status_code, 200, path)
        self.client.post('/store/', {'payload': 'via web', 'blockchain': 'RBB'})
        self.assertTrue(RequestLog.objects.filter(user=self.user, source='web', endpoint='store', status_code=200).exists())

    def test_register_creates_account_and_logs_in(self):
        c = Client()
        r = c.post('/register/', {'username': 'carla', 'password1': 'Uma-senha-boa-9', 'password2': 'Uma-senha-boa-9'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(c.get('/').status_code, 200)
        weak = Client().post('/register/', {'username': 'dan', 'password1': '123', 'password2': '123'})
        self.assertEqual(weak.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username='dan').exists())


class CostFormulaTests(SimpleTestCase):
    def test_fernet_size_formula_matches_real_tokens(self):
        f = Fernet(Fernet.generate_key())
        for n in list(range(0, 70)) + [255, 256, 1000, 4096]:
            self.assertEqual(costs.fernet_token_size(n), len(f.encrypt(b'a' * n)), n)

    def test_ethereum_gas(self):
        self.assertEqual(costs.eth_gas(100), 21000 + 10 * 400)         # piso EIP-7623
        self.assertEqual(costs.eth_gas(100, zero_bytes=100), 21000 + 10 * 100)

    def test_bitcoin_vsize(self):
        self.assertEqual(costs.btc_vsize(80), 202)
        self.assertEqual(costs.btc_vsize(20), 141)

    def test_stellar_fee_is_per_operation_not_per_byte(self):
        r = costs.estimate('STELLAR', payload='abc')
        self.assertAlmostEqual(r['fee_native'], 100 / 1e7)

    def test_fragmentation_and_feasibility(self):
        r = costs.estimate('STELLAR', payload='x' * 100)
        self.assertEqual(r['fragments'], 4)
        self.assertFalse(r['feasible'])
        self.assertTrue(costs.estimate('STELLAR', payload='x' * 100, multiple_tx=True)['feasible'])

    def test_encryption_increases_onchain_size(self):
        r = costs.estimate('ETHEREUM', size_bytes=10, encrypted=True)
        self.assertEqual(r['onchain_bytes'], 100)

    def test_free_networks_cost_zero(self):
        for chain in ('RBB', 'POSTGRES', 'MULTICHAIN', 'EOS'):
            self.assertEqual(costs.estimate(chain, payload='x')['fee_usd'], 0)

    def test_params_are_validated_and_applied(self):
        with self.assertRaises(ValueError):
            costs.resolve_params({'gas_price_gwei': -1})
        with self.assertRaises(ValueError):
            costs.resolve_params({'fee_rate_sat_vb': 'abc'})
        cheap = costs.estimate('ETHEREUM', payload='x', params=costs.resolve_params({'gas_price_gwei': 1}))
        dear = costs.estimate('ETHEREUM', payload='x', params=costs.resolve_params({'gas_price_gwei': 10}))
        self.assertAlmostEqual(dear['fee_native'], cheap['fee_native'] * 10)

    def test_estimate_requires_size(self):
        with self.assertRaises(ValueError):
            costs.estimate('ETHEREUM')

    def test_estimate_all_is_sorted_by_cost(self):
        usd = [r['fee_usd'] for r in costs.estimate_all(payload='oi', multiple_tx=True)]
        self.assertEqual(usd, sorted(usd))


class CalculatorAndAdminTests(LedgerMixin, TestCase):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.ana = User.objects.create_user('ana', password='Senha-forte-123')
        self.beto = User.objects.create_user('beto', password='Senha-forte-123')
        self.admin = User.objects.create_user('root', password='Senha-forte-123', is_staff=True, is_superuser=True)

    def store_as(self, user, payload, chain, **extra):
        c = Client()
        c.force_login(user)
        return c.post('/store/', {'payload': payload, 'blockchain': chain, **extra})

    def preview(self, url, body, user=None):
        c = Client()
        c.force_login(user or self.ana)
        return c.post(url, data=json.dumps(body), content_type='application/json')

    def test_calculator_tab_is_gone(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get('/calculadora/').status_code, 404)
        self.assertNotContains(self.client.get('/store/'), 'Calculadora')

    def test_store_form_shows_cost_panel_and_script(self):
        self.client.force_login(self.ana)
        page = self.client.get('/store/')
        self.assertContains(page, 'id="cost-panel"')
        self.assertContains(page, 'js/cost_preview.js')
        self.assertContains(page, '/custo/gravar/')
        self.assertContains(self.client.get('/migrate/'), '/custo/migrar/')

    def test_store_preview_returns_price_before_sending(self):
        r = self.preview('/custo/gravar/', {'blockchain': 'ETHEREUM', 'payload': 'x' * 60})
        data = r.json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(data['selected']['blockchain'], 'ETHEREUM')
        self.assertEqual(data['selected']['fragments'], 1)
        self.assertGreater(data['selected']['fee_usd'], 0)
        self.assertEqual(len(data['options']), 7)
        self.assertEqual(data['cheapest']['fee_usd'], 0)
        self.assertIn('gwei', data['assumptions'])
        self.assertEqual(RequestLog.objects.count(), 0)  # a prévia não é contabilizada

    def test_store_preview_matches_what_is_recorded_after_sending(self):
        quoted = self.preview('/custo/gravar/', {'blockchain': 'BITCOIN', 'payload': 'y' * 70}).json()['selected']
        self.store_as(self.ana, 'y' * 70, 'BITCOIN')
        log = RequestLog.objects.get(endpoint='store')
        self.assertAlmostEqual(log.cost_usd, quoted['fee_usd'])
        self.assertEqual(log.tx_count, quoted['fragments'])

    def test_store_preview_flags_fragmentation_and_encryption(self):
        blocked = self.preview('/custo/gravar/', {'blockchain': 'STELLAR', 'payload': 'x' * 100}).json()['selected']
        self.assertFalse(blocked['feasible'])
        self.assertEqual(blocked['fragments'], 4)
        ok = self.preview('/custo/gravar/', {'blockchain': 'STELLAR', 'payload': 'x' * 100, 'multiple_tx': True}).json()['selected']
        self.assertTrue(ok['feasible'])
        enc = self.preview('/custo/gravar/', {'blockchain': 'ETHEREUM', 'payload': 'x' * 10, 'encrypted': True}).json()['selected']
        self.assertEqual(enc['onchain_bytes'], 100)

    def test_store_preview_validation_and_auth(self):
        self.assertEqual(self.preview('/custo/gravar/', {'blockchain': 'ETHEREUM', 'payload': '  '}).status_code, 400)
        self.assertEqual(self.preview('/custo/gravar/', {'blockchain': 'XYZ', 'payload': 'a'}).status_code, 400)
        self.assertEqual(self.preview('/custo/gravar/', {'blockchain': 'HYPERLEDGER', 'payload': 'a'}).status_code, 400)
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get('/custo/gravar/').status_code, 400)
        self.assertEqual(Client().post('/custo/gravar/', data='{}', content_type='application/json').status_code, 302)

    def test_migrate_preview_uses_source_size_and_owner(self):
        h = api.store('m' * 100, 'RBB', owner=self.ana.pk)[0]
        r = self.preview('/custo/migrar/', {'source_hash': h, 'target_blockchain': 'STELLAR', 'multiple_tx': True})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['selected']['fragments'], 4)
        self.assertEqual(self.preview('/custo/migrar/', {'source_hash': h, 'target_blockchain': 'STELLAR'}, user=self.beto).status_code, 404)
        self.assertEqual(self.preview('/custo/migrar/', {'source_hash': 'nao-existe', 'target_blockchain': 'STELLAR'}).status_code, 404)
        self.assertEqual(self.preview('/custo/migrar/', {'source_hash': '', 'target_blockchain': 'STELLAR'}).status_code, 400)

    def test_api_estimate(self):
        c = Client()
        c.force_login(self.ana)
        key = c.post('/account/api-key/').context['new_api_key']
        r = c.post('/api/estimate/', data=json.dumps({'size_bytes': 500, 'encrypted': True, 'multiple_tx': True}),
                   content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {key}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()['estimates']), 7)
        bad = c.post('/api/estimate/', data=json.dumps({}), content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {key}')
        self.assertEqual(bad.status_code, 400)

    def test_store_records_cost_for_accounting(self):
        self.store_as(self.ana, 'x' * 60, 'ETHEREUM')
        log = RequestLog.objects.get(user=self.ana, endpoint='store')
        self.assertEqual(log.blockchain, 'ETHEREUM')
        self.assertEqual(log.tx_count, 1)
        self.assertEqual(log.bytes_stored, 60)
        self.assertAlmostEqual(log.cost_usd, costs.estimate('ETHEREUM', payload='x' * 60)['fee_usd'])

    def test_failed_store_costs_nothing(self):
        self.store_as(self.ana, 'x' * 100, 'STELLAR')  # sem multiple_tx: erro de tamanho
        log = RequestLog.objects.get(user=self.ana, endpoint='store')
        self.assertEqual(log.status_code, 400)
        self.assertEqual((log.tx_count, log.cost_usd), (0, 0))

    def test_admin_area_is_staff_only(self):
        self.assertEqual(Client().get('/painel-admin/').status_code, 302)
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get('/painel-admin/').status_code, 403)
        self.assertNotContains(self.client.get('/'), 'Contabilidade (Admin)')
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/painel-admin/').status_code, 200)
        self.assertContains(self.client.get('/'), 'Contabilidade (Admin)')
        # usuário comum nunca vê o link nem entra por URL direta, em nenhuma tela
        self.client.force_login(self.ana)
        for path in ('/', '/store/', '/migrate/', '/account/'):
            self.assertNotContains(self.client.get(path), 'painel-admin', msg_prefix=path)

    def test_admin_ranking_orders_chains_by_spend(self):
        self.store_as(self.ana, 'x' * 70, 'BITCOIN')
        self.store_as(self.ana, 'y' * 70, 'ETHEREUM')
        self.store_as(self.beto, 'z' * 70, 'ETHEREUM')
        self.store_as(self.beto, 'w' * 70, 'RBB')
        self.client.force_login(self.admin)
        r = self.client.get('/painel-admin/')
        chains = [c['blockchain'] for c in r.context['chains']]
        # 1 tx BTC (~US$ 1,15) custa mais que 2 tx ETH (~US$ 0,71); RBB não tem taxa
        self.assertEqual(chains, ['BITCOIN', 'ETHEREUM', 'RBB'])
        self.assertEqual(r.context['top_chain']['blockchain'], 'BITCOIN')
        eth = r.context['chains'][1]
        self.assertEqual((eth['users'], eth['txs'], eth['ops']), (2, 2, 2))
        self.assertEqual({u['user__username'] for u in r.context['top_users']}, {'ana', 'beto'})
        self.assertEqual(r.context['top_users'][0]['user__username'], 'ana')
        by_txs = self.client.get('/painel-admin/', {'order': 'txs'}).context['chains']
        self.assertEqual(by_txs[0]['blockchain'], 'ETHEREUM')

    def test_admin_period_and_invalid_params(self):
        self.store_as(self.ana, 'x' * 70, 'ETHEREUM')
        RequestLog.objects.update(created_at=timezone.now() - datetime.timedelta(days=60))
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/painel-admin/', {'period': '30'}).context['chains'], [])
        self.assertEqual(len(self.client.get('/painel-admin/', {'period': 'all'}).context['chains']), 1)
        self.assertEqual(self.client.get('/painel-admin/', {'period': 'x', 'order': 'y'}).status_code, 200)

    def test_create_admin_command(self):
        from io import StringIO
        from django.core.management import call_command
        from django.core.management.base import CommandError
        out = StringIO()
        call_command('create_admin', '--username', 'chefe', stdout=out)
        user = get_user_model().objects.get(username='chefe')
        self.assertTrue(user.is_staff and user.is_superuser)
        self.assertIn('Senha gerada', out.getvalue())
        with self.assertRaises(CommandError):
            call_command('create_admin', '--username', 'chefe', stdout=StringIO())
        call_command('create_admin', '--username', 'chefe', '--reset', '--password', 'Nova-senha-123', stdout=StringIO())
        self.assertTrue(get_user_model().objects.get(username='chefe').check_password('Nova-senha-123'))


class WalletTests(LedgerMixin, TestCase):
    """UC05/FR11: painel de credenciais de rede (Carteira), sem chaves privadas."""

    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.ana = User.objects.create_user('ana', password='Senha-forte-123')
        self.beto = User.objects.create_user('beto', password='Senha-forte-123')

    def test_add_list_rename_delete_credential(self):
        self.client.force_login(self.ana)
        r = self.client.post('/carteira/', {'blockchain': 'ETHEREUM', 'label': 'Minha carteira', 'external_id': '0xabc'})
        self.assertEqual(r.status_code, 302)
        cred = NetworkCredential.objects.get(user=self.ana)
        self.assertEqual((cred.blockchain, cred.label, cred.external_id), ('ETHEREUM', 'Minha carteira', '0xabc'))
        self.assertContains(self.client.get('/carteira/'), 'Minha carteira')

        self.client.post(f'/carteira/{cred.pk}/renomear/', {'label': 'Renomeada', 'external_id': '0xdef'})
        cred.refresh_from_db()
        self.assertEqual((cred.label, cred.external_id), ('Renomeada', '0xdef'))

        self.client.post(f'/carteira/{cred.pk}/remover/')
        self.assertFalse(NetworkCredential.objects.filter(pk=cred.pk).exists())

    def test_invalid_blockchain_and_empty_label_are_rejected(self):
        self.client.force_login(self.ana)
        self.client.post('/carteira/', {'blockchain': 'XYZ', 'label': 'x'})
        self.client.post('/carteira/', {'blockchain': 'RBB', 'label': ''})
        self.assertEqual(NetworkCredential.objects.count(), 0)

    def test_users_cannot_manage_each_others_credentials(self):
        self.client.force_login(self.ana)
        self.client.post('/carteira/', {'blockchain': 'RBB', 'label': 'Da Ana'})
        cred = NetworkCredential.objects.get(user=self.ana)

        intruder = Client()
        intruder.force_login(self.beto)
        intruder.post(f'/carteira/{cred.pk}/renomear/', {'label': 'Invadido'})
        cred.refresh_from_db()
        self.assertEqual(cred.label, 'Da Ana')

        intruder.post(f'/carteira/{cred.pk}/remover/')
        self.assertTrue(NetworkCredential.objects.filter(pk=cred.pk).exists())

    def test_wallet_requires_login(self):
        self.assertEqual(Client().get('/carteira/').status_code, 302)


class BillingTests(LedgerMixin, TestCase):
    """UC10/FR17: histórico de custo consolidado pessoal (Meu Consumo)."""

    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.ana = User.objects.create_user('ana', password='Senha-forte-123')
        self.beto = User.objects.create_user('beto', password='Senha-forte-123')

    def store_as(self, user, payload, chain, **extra):
        c = Client()
        c.force_login(user)
        return c.post('/store/', {'payload': payload, 'blockchain': chain, **extra})

    def test_billing_shows_only_own_operations(self):
        self.store_as(self.ana, 'x' * 70, 'BITCOIN')
        self.store_as(self.beto, 'y' * 70, 'ETHEREUM')
        self.client.force_login(self.ana)
        chains = [c['blockchain'] for c in self.client.get('/consumo/').context['chains']]
        self.assertEqual(chains, ['BITCOIN'])

    def test_billing_filters_by_blockchain(self):
        self.store_as(self.ana, 'x' * 70, 'BITCOIN')
        self.store_as(self.ana, 'y' * 70, 'ETHEREUM')
        self.client.force_login(self.ana)
        chains = [c['blockchain'] for c in self.client.get('/consumo/', {'blockchain': 'ETHEREUM'}).context['chains']]
        self.assertEqual(chains, ['ETHEREUM'])

    def test_billing_filters_by_period(self):
        self.store_as(self.ana, 'x' * 70, 'BITCOIN')
        RequestLog.objects.update(created_at=timezone.now() - datetime.timedelta(days=60))
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get('/consumo/', {'period': '30'}).context['chains'], [])
        self.assertEqual(len(self.client.get('/consumo/', {'period': 'all'}).context['chains']), 1)

    def test_billing_totals_match_admin_totals_for_same_user(self):
        self.store_as(self.ana, 'x' * 70, 'BITCOIN')
        self.client.force_login(self.ana)
        mine = self.client.get('/consumo/').context['totals']['cost']
        self.assertAlmostEqual(mine, costs.estimate('BITCOIN', payload='x' * 70)['fee_usd'])

    def test_billing_requires_login(self):
        self.assertEqual(Client().get('/consumo/').status_code, 302)


class ApiKeyRevokeTests(LedgerMixin, TestCase):
    """UC06: revogar chave de API, além de gerar uma nova."""

    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.ana = User.objects.create_user('ana', password='Senha-forte-123')

    def test_revoke_deletes_key_and_blocks_api_access(self):
        c = Client()
        c.force_login(self.ana)
        key = c.post('/account/api-key/').context['new_api_key']
        self.assertEqual(c.get('/api/transactions/', HTTP_AUTHORIZATION=f'Bearer {key}').status_code, 200)

        c.post('/account/api-key/revogar/')
        self.assertFalse(ApiKey.objects.filter(user=self.ana).exists())
        self.assertEqual(Client().get('/api/transactions/', HTTP_AUTHORIZATION=f'Bearer {key}').status_code, 401)

    def test_revoke_without_key_is_harmless(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.post('/account/api-key/revogar/').status_code, 200)


class IncrementalStoreTests(LedgerMixin, TestCase):
    """FR10: progresso real fragmento a fragmento para o Store (/store/iniciar/, /store/passo/)."""

    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.ana = User.objects.create_user('ana', password='Senha-forte-123')
        self.beto = User.objects.create_user('beto', password='Senha-forte-123')
        self.client.force_login(self.ana)

    def start(self, body):
        return self.client.post('/store/iniciar/', data=json.dumps(body), content_type='application/json')

    def step(self):
        return self.client.post('/store/passo/')

    def run_full(self, body):
        total = self.start(body).json()['total']
        last = None
        for _ in range(total):
            last = self.step()
        return last

    def test_single_fragment_matches_sync_result(self):
        data = self.run_full({'blockchain': 'RBB', 'payload': 'olá mundo'}).json()
        self.assertTrue(data['done'])
        self.assertEqual(data['count'], 1)
        self.assertEqual(api.retrieve(data['hashes'][0])['payload'], 'olá mundo')

    def test_multi_fragment_reports_progress_and_reassembles(self):
        text = 'x' * 100
        total = self.start({'blockchain': 'STELLAR', 'payload': text, 'multiple_tx': True}).json()['total']
        self.assertGreater(total, 1)
        for i in range(total - 1):
            r = self.step().json()
            self.assertFalse(r['done'])
            self.assertEqual(r['progress'], i + 1)
        data = self.step().json()
        self.assertTrue(data['done'])
        self.assertEqual(data['count'], total)
        self.assertEqual(api.retrieve(data['hashes'][0])['payload'], text)

    def test_encrypted_store_is_decryptable(self):
        data = self.run_full({'blockchain': 'RBB', 'payload': 'segredo', 'password': 'pw'}).json()
        self.assertTrue(data['encrypted'])
        self.assertEqual(api.retrieve(data['hashes'][0], pw='pw')['payload'], 'segredo')

    def test_redundancy_creates_postgres_copy(self):
        data = self.run_full({'blockchain': 'RBB', 'payload': 'espelho', 'redundancy': True}).json()
        self.assertEqual(data['count'], 2)
        self.assertEqual(api.retrieve(data['hashes'][1])['blockchain'], 'POSTGRES')

    def test_oversized_without_multiple_tx_returns_error(self):
        self.assertEqual(self.start({'blockchain': 'STELLAR', 'payload': 'x' * 100}).status_code, 400)

    def test_empty_payload_returns_error(self):
        self.assertEqual(self.start({'blockchain': 'RBB', 'payload': ''}).status_code, 400)

    def test_step_without_start_is_error(self):
        self.assertEqual(self.step().status_code, 400)

    def test_completed_operation_is_accounted(self):
        self.run_full({'blockchain': 'ETHEREUM', 'payload': 'x' * 60})
        log = RequestLog.objects.get(user=self.ana, endpoint='store', source='web')
        self.assertEqual(log.status_code, 200)
        self.assertEqual(log.blockchain, 'ETHEREUM')

    def test_job_does_not_leak_to_other_sessions(self):
        self.start({'blockchain': 'RBB', 'payload': 'a'})
        other = Client()
        other.force_login(self.beto)
        self.assertEqual(other.post('/store/passo/').status_code, 400)


class IncrementalMigrateTests(LedgerMixin, TestCase):
    """FR10: progresso real fragmento a fragmento para o Migrate (/migrate/iniciar/, /migrate/passo/)."""

    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.ana = User.objects.create_user('ana', password='Senha-forte-123')
        self.beto = User.objects.create_user('beto', password='Senha-forte-123')
        self.client.force_login(self.ana)

    def start(self, body):
        return self.client.post('/migrate/iniciar/', data=json.dumps(body), content_type='application/json')

    def step(self):
        return self.client.post('/migrate/passo/')

    def run_full(self, body):
        total = self.start(body).json()['total']
        last = None
        for _ in range(total):
            last = self.step()
        return last

    def test_migrate_preserves_encryption(self):
        src = api.store('dado cifrado', 'RBB', pw='abc', owner=self.ana.pk)[0]
        data = self.run_full({'source_hash': src, 'target_blockchain': 'ETHEREUM'}).json()
        self.assertTrue(data['done'])
        self.assertEqual(api.retrieve(data['new_hashes'][0], pw='abc')['payload'], 'dado cifrado')

    def test_migrate_fragments_when_needed(self):
        src = api.store('a' * 200, 'RBB', owner=self.ana.pk)[0]
        total = self.start({'source_hash': src, 'target_blockchain': 'STELLAR', 'multiple_tx': True}).json()['total']
        self.assertGreater(total, 1)
        data = None
        for _ in range(total):
            data = self.step().json()
        self.assertEqual(len(data['new_hashes']), total)
        self.assertEqual(api.retrieve(data['new_hashes'][0])['payload'], 'a' * 200)

    def test_migrate_owner_isolation(self):
        src = api.store('privado', 'RBB', owner=self.beto.pk)[0]
        self.assertEqual(self.start({'source_hash': src, 'target_blockchain': 'ETHEREUM'}).status_code, 404)

    def test_migrate_without_multiple_tx_returns_error(self):
        src = api.store('a' * 200, 'RBB', owner=self.ana.pk)[0]
        self.assertEqual(self.start({'source_hash': src, 'target_blockchain': 'STELLAR'}).status_code, 400)

    def test_missing_source_hash_returns_error(self):
        self.assertEqual(self.start({'source_hash': '', 'target_blockchain': 'ETHEREUM'}).status_code, 400)

    def test_migrate_is_accounted(self):
        src = api.store('x' * 60, 'RBB', owner=self.ana.pk)[0]
        self.run_full({'source_hash': src, 'target_blockchain': 'ETHEREUM'})
        log = RequestLog.objects.get(user=self.ana, endpoint='migrate', source='web')
        self.assertEqual(log.status_code, 200)
        self.assertEqual(log.blockchain, 'ETHEREUM')
