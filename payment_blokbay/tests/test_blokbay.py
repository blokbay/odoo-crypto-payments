# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
import hashlib
import hmac
import json
import time
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment.tests.common import PaymentCommon

SECRET = 'whsec_' + 'k' * 40


def sign(raw, secret=SECRET, ts=None):
    ts = ts or int(time.time())
    return 't=%s,v1=%s' % (ts, hmac.new(secret.encode(), b'%d.' % ts + raw, hashlib.sha256).hexdigest())


@tagged('post_install', '-at_install', 'blokbay')
class TestBlokbay(PaymentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.currency_usd = cls.env.ref('base.USD')
        cls.currency_usd.active = True
        cls.provider = cls._prepare_provider('blokbay', update_values={
            'blokbay_public_key': 'pk_live_abc123def456',
            'blokbay_secret_key': 'sk_live_' + 'a1' * 24,
            'blokbay_webhook_secret': SECRET,
        })
        cls.currency = cls.currency_usd
        cls.payment_method = cls.env.ref('payment_blokbay.payment_method_blokbay_crypto')
        cls.payment_method_id = cls.payment_method.id

    def _tx(self, **kw):
        return self._create_transaction('redirect', currency_id=self.currency_usd.id, amount=249.9, **kw)

    def test_signature(self):
        raw = b'{"type":"ping"}'
        self.assertTrue(self.provider._blokbay_verify_signature(raw, sign(raw)))
        self.assertFalse(self.provider._blokbay_verify_signature(raw, sign(raw, secret='whsec_other')))
        self.assertFalse(self.provider._blokbay_verify_signature(raw, sign(raw, ts=int(time.time()) - 1000)))
        self.assertFalse(self.provider._blokbay_verify_signature(raw, 'garbage'))

    def test_currencies_and_no_validation(self):
        names = set(self.provider._get_supported_currencies().mapped('name'))
        self.assertTrue({'USD', 'EUR', 'JPY'} <= names or 'USD' in names)
        self.assertTrue(names <= {'USD', 'EUR', 'GBP', 'CHF', 'JPY', 'CAD', 'AUD', 'SGD', 'HKD', 'AED'})
        method_currencies = set(self.payment_method.with_context(active_test=False).supported_currency_ids.mapped('name'))
        self.assertEqual(method_currencies, {'USD', 'EUR', 'GBP', 'CHF', 'JPY', 'CAD', 'AUD', 'SGD', 'HKD', 'AED'})
        self.assertEqual(self.provider._get_default_payment_method_codes(), {'blokbay_crypto'})

    def _rendered(self, tx):
        calls = []

        def fake(method, path, payload=None, idempotency_key=None):
            calls.append((method, path, payload, idempotency_key))
            return {'id': 'gp_abcdef123456', 'url': 'https://blokbay.com/pay/gp_abcdef123456', 'status': 'pending'}
        with patch.object(type(self.provider), '_blokbay_request', autospec=True, side_effect=lambda _self, *a, **k: fake(*a, **k)):
            tx._get_specific_rendering_values({})
        return calls[0]

    def test_eur_and_jpy(self):
        eur = self.env.ref('base.EUR'); eur.active = True
        jpy = self.env.ref('base.JPY'); jpy.active = True
        tx = self._create_transaction('redirect', reference='EUR1', currency_id=eur.id, amount=249.9)
        _m, _p, payload, idem = self._rendered(tx)
        self.assertEqual((payload['amount'], payload['currency'], idem), ('249.90', 'EUR', 'odoo:EUR1:EUR'))
        tx_j = self._create_transaction('redirect', reference='JPY1', currency_id=jpy.id, amount=25000)
        _m, _p, payload, idem = self._rendered(tx_j)
        self.assertEqual((payload['amount'], payload['currency']), ('25000', 'JPY'))
        # webhook in the same currency: paid; other currency or amount: error
        tx.provider_reference = 'gp_abcdef123456'
        base = {'id': 'gp_abcdef123456', 'reference': 'EUR1', 'amount': '249.90', 'currency': 'EUR', 'status': 'paid'}
        self._process(tx, dict(base, currency='USD'))
        self.assertEqual(tx.state, 'error')
        tx2 = self._create_transaction('redirect', reference='EUR2', currency_id=eur.id, amount=249.9, provider_reference='gp_abcdef222222')
        self._process(tx2, dict(base, id='gp_abcdef222222', reference='EUR2'))
        self.assertEqual(tx2.state, 'done')
        tx_j.provider_reference = 'gp_abcdef333333'
        self._process(tx_j, {'id': 'gp_abcdef333333', 'reference': 'JPY1', 'amount': '25000', 'currency': 'JPY', 'status': 'paid'})
        self.assertEqual(tx_j.state, 'done')

    def test_unsupported_currency(self):
        sek = self.env.ref('base.SEK'); sek.active = True
        tx = self._create_transaction('redirect', reference='SEK1', currency_id=sek.id, amount=100)
        with self.assertRaises(ValidationError):
            tx._get_specific_rendering_values({})
        self.assertNotIn('SEK', self.provider._get_supported_currencies().mapped('name'))

    def test_rendering_creates_payment_with_idempotency(self):
        tx = self._tx()
        calls = []

        def fake(method, path, payload=None, idempotency_key=None):
            calls.append((method, path, payload, idempotency_key))
            return {'id': 'gp_abcdef123456', 'url': 'https://blokbay.com/pay/gp_abcdef123456', 'status': 'pending'}
        with patch.object(type(self.provider), '_blokbay_request', autospec=True, side_effect=lambda _self, *a, **k: fake(*a, **k)):
            values = tx._get_specific_rendering_values({})
        self.assertEqual(values['api_url'], 'https://blokbay.com/pay/gp_abcdef123456')
        self.assertEqual(tx.provider_reference, 'gp_abcdef123456')
        method, path, payload, idem = calls[0]
        self.assertEqual((method, path, idem), ('POST', '/api/v1/payments', 'odoo:' + tx.reference))
        self.assertEqual(payload['amount'], '249.90')
        self.assertEqual(payload['currency'], 'USD')
        self.assertIn('/payment/blokbay/return?ref=', payload['url_success'])

    def _process(self, tx, api_payment, data=None):
        with patch.object(type(self.provider), '_blokbay_get_payment', return_value=api_payment):
            tx._handle_notification_data('blokbay', data or {'reference': tx.reference})

    def test_paid_expired_mismatch(self):
        tx = self._tx(provider_reference='gp_abcdef123456')
        base = {'id': 'gp_abcdef123456', 'reference': tx.reference, 'amount': '249.90', 'currency': 'USD'}
        self._process(tx, dict(base, status='pending'))
        self.assertEqual(tx.state, 'pending')
        self._process(tx, dict(base, status='paid', tx='0x' + 'ab' * 32, network='Polygon', coin='USDC'))
        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.blokbay_coin, 'USDC')
        self._process(tx, dict(base, status='paid', tx='0x' + 'ab' * 32))  # same event again
        self.assertEqual(tx.state, 'done')
        tx2 = self._tx(reference='R2', provider_reference='gp_abcdef654321')
        self._process(tx2, dict(base, id='gp_abcdef654321', reference='R2', status='expired'))
        self.assertEqual(tx2.state, 'cancel')
        self._process(tx2, dict(base, id='gp_abcdef654321', reference='R2', status='paid'))  # late payment after expiry
        self.assertEqual(tx2.state, 'done')
        tx3 = self._tx(reference='R3', provider_reference='gp_abcdef999999')
        self._process(tx3, dict(base, id='gp_abcdef999999', reference='R3', status='paid', amount='1.00'))
        self.assertEqual(tx3.state, 'error')

    def test_payment_must_match_transaction(self):
        tx = self._tx(provider_reference='gp_abcdef123456')
        with self.assertRaises(ValidationError):
            self._process(tx, {'id': 'gp_abcdef123456', 'reference': 'OTHER', 'status': 'paid', 'amount': '249.90', 'currency': 'USD'})
        self.assertNotEqual(tx.state, 'done')
