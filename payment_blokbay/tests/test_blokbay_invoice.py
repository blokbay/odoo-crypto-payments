# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

URL = 'https://blokbay.com/i/' + 'a' * 64


@tagged('post_install', '-at_install', 'blokbay')
class TestBlokbayInvoice(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls, *args, **kwargs):
        super().setUpClass(*args, **kwargs)
        company = cls.company_data['company']
        cls.provider = cls.env.ref('payment_blokbay.payment_provider_blokbay').sudo().copy({
            'company_id': company.id, 'state': 'test', 'blokbay_public_key': 'pk_live_abc123def456',
            'blokbay_secret_key': 'sk_live_' + 'a1' * 24, 'blokbay_webhook_secret': 'whsec_' + 'k' * 40,
        })
        cls.partner_a.email = 'ap@client.example'
        cls.invoice = cls.init_invoice('out_invoice', partner=cls.partner_a, amounts=[100.0, 50.0], taxes=cls.tax_sale_a, post=True)

    def _create(self, move, answers=None):
        calls = []
        answers = list(answers or [{'id': 'inv_abc123def', 'url': URL, 'number': move.name, 'status': 'open'}])

        def fake(provider, method, path, payload=None, idempotency_key=None):
            calls.append({'method': method, 'path': path, 'payload': payload, 'key': idempotency_key})
            a = answers.pop(0)
            if isinstance(a, Exception):
                raise a
            return a
        with patch.object(type(self.provider), '_blokbay_request', fake):
            move.action_blokbay_invoice()
        return calls

    def test_button_creates_invoice_with_the_same_total(self):
        move = self.invoice
        self.assertTrue(move._blokbay_can_pay())
        calls = self._create(move)
        self.assertEqual(calls[0]['path'], '/api/v1/invoices')
        p = calls[0]['payload']
        total = sum(float(l['unit_price']) * float(l['quantity']) for l in p['lines'])
        self.assertAlmostEqual(total, move.amount_total, places=2)
        self.assertEqual(p['customer']['email'], 'ap@client.example')
        self.assertEqual(p['currency'], move.currency_id.name)
        self.assertEqual(p['external_ref'], 'odoo:%s' % move.name)
        self.assertNotIn('send', p)
        self.assertTrue(calls[0]['key'].startswith('odoo-invoice:%s:' % move.id))
        self.assertEqual(move.blokbay_invoice_status, 'open')
        self.assertEqual(move.blokbay_payment_url, URL)
        self.assertFalse(move._blokbay_can_pay())
        # Link in the invoice email and in the PDF.
        template = self.env.ref('account.email_template_edi_invoice')
        body = self.env['account.move.send']._get_default_mail_body(move, template, 'en_US')
        self.assertIn(URL, str(body))
        html = self.env['ir.actions.report']._render_qweb_html('account.report_invoice', move.ids)[0]
        self.assertIn(URL.encode(), html)

    def test_number_already_used_falls_back_to_automatic(self):
        move = self.invoice
        calls = self._create(move, [ValidationError('Blokbay: number: already used by another invoice.'), {'id': 'inv_abc123zzz', 'url': URL, 'number': '2026-0001'}])
        self.assertIn('number', calls[0]['payload'])
        self.assertNotIn('number', calls[1]['payload'])
        self.assertEqual(move.blokbay_invoice_id, 'inv_abc123zzz')

    def test_paid_event_registers_the_payment_once(self):
        move = self.invoice
        self._create(move)
        data = {'id': 'inv_abc123def', 'status': 'paid', 'total': '%.2f' % move.amount_total, 'currency': move.currency_id.name, 'number': move.name,
                'payment': {'coin': 'USDC', 'network': 'Base', 'tx': '0x' + 'ab' * 32, 'paid_at': '2026-11-25T12:00:00.000Z'}}
        self.assertEqual(move._blokbay_apply_invoice(self.provider, data), 'paid')
        self.assertIn(move.payment_state, ('paid', 'in_payment'))
        self.assertEqual(move.blokbay_invoice_status, 'paid')
        self.assertEqual(move._blokbay_apply_invoice(self.provider, data), 'duplicate')

    def test_void_event_and_checks(self):
        move = self.invoice
        self._create(move)
        self.assertEqual(move._blokbay_apply_invoice(self.provider, {'id': 'inv_abc123def', 'status': 'void'}), 'void')
        self.assertFalse(move.blokbay_payment_url)
        self.assertTrue(move._blokbay_can_pay(), 'a new link can be created after a cancelled one')
        draft = self.init_invoice('out_invoice', partner=self.partner_a, amounts=[10.0])
        with self.assertRaises(UserError):
            draft.action_blokbay_invoice()
        self.partner_b.email = False
        no_mail = self.init_invoice('out_invoice', partner=self.partner_b, amounts=[10.0], post=True)
        with self.assertRaises(UserError):
            no_mail._blokbay_invoice_payload()
