# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Stablecoin invoices: the "Pay with Blokbay" button on customer invoices.

The button creates a Blokbay invoice (POST /api/v1/invoices) with the lines, taxes and customer of the Odoo invoice, keeps the payment
link on the invoice (form, PDF and invoice email) and registers the payment when the signed webhook invoice.paid arrives (the invoice
is read again from the API first). It uses the keys of the Blokbay payment provider of the company: the eCommerce payment method keeps
working as before.
"""
import logging
import re

from markupsafe import Markup, escape

from odoo import _, fields, models, release
from odoo.exceptions import UserError, ValidationError

from odoo.addons.payment_blokbay import const

_logger = logging.getLogger(__name__)

INVOICE_ID_RE = re.compile(r'^inv_[a-z0-9]{6,40}$')
PAY_URL_RE = re.compile(r'^https://[^\s"<>]+/i/[0-9a-f]{64}$')


class AccountMove(models.Model):
    _inherit = 'account.move'

    blokbay_invoice_id = fields.Char(string="Blokbay Invoice", copy=False, readonly=True)
    blokbay_payment_url = fields.Char(string="Blokbay Payment Link", copy=False, readonly=True)
    blokbay_invoice_status = fields.Selection(
        [('open', "Waiting for payment"), ('paid', "Paid"), ('void', "Cancelled")],
        string="Blokbay Status", copy=False, readonly=True,
    )
    blokbay_attempt = fields.Integer(copy=False, default=0)

    def _blokbay_provider(self):
        self.ensure_one()
        provider = self.env['payment.provider'].sudo().search([
            ('code', '=', 'blokbay'), ('state', '!=', 'disabled'), ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not provider:
            raise UserError(_("Enable the Blokbay payment provider of this company first (Accounting > Configuration > Payment Providers)."))
        return provider

    def _blokbay_can_pay(self):
        self.ensure_one()
        return (self.move_type == 'out_invoice' and self.state == 'posted' and self.payment_state not in ('paid', 'in_payment', 'reversed')
                and self.blokbay_invoice_status != 'open')

    def _blokbay_invoice_payload(self):
        """ Customer, lines and taxes of the Odoo invoice. Each product line goes with its subtotal (discounts included) and the taxes
        as one line, so the Blokbay total is exactly the Odoo total. """
        self.ensure_one()
        currency = self.currency_id
        if currency.name not in const.SUPPORTED_CURRENCIES:
            raise UserError(_("Blokbay invoices accept %(accepted)s, not %(currency)s.", accepted=', '.join(const.SUPPORTED_CURRENCIES), currency=currency.name))
        decimals = const.CURRENCY_DECIMALS[currency.name]
        fmt = lambda v: ('%.' + str(decimals) + 'f') % currency.round(v)
        partner = self.partner_id
        email = (partner.email or self.commercial_partner_id.email or '').strip()
        if not email:
            raise UserError(_("Add an email address to the customer: Blokbay needs it for the payment link."))
        lines = []
        for line in self.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
            if currency.is_zero(line.price_subtotal):
                continue
            qty = line.quantity or 1.0
            exact = not line.discount and currency.compare_amounts(currency.round(qty * line.price_unit), line.price_subtotal) == 0
            name = re.sub(r'\s+', ' ', (line.name or line.product_id.display_name or _("Item"))).strip()[:250]
            if exact and qty > 0:
                lines.append({'description': name, 'quantity': ('%.3f' % qty).rstrip('0').rstrip('.'), 'unit_price': fmt(line.price_unit), 'tax_rate': 0})
            else:
                lines.append({'description': ('%s (%s)' % (name, ('%.3f' % qty).rstrip('0').rstrip('.')))[:300], 'quantity': 1, 'unit_price': fmt(line.price_subtotal), 'tax_rate': 0})
        if not currency.is_zero(self.amount_tax):
            lines.append({'description': _("Taxes"), 'quantity': 1, 'unit_price': fmt(self.amount_tax), 'tax_rate': 0})
        if not lines:
            raise UserError(_("The invoice has no amount to pay."))
        address = ', '.join(p for p in [partner.street, partner.zip, partner.city, partner.country_id.name] if p)[:500]
        payload = {
            'customer': {'name': (self.commercial_partner_id.name or partner.name or '')[:200], 'email': email[:200], 'address': address, 'tax_id': (self.commercial_partner_id.vat or '')[:60]},
            'issuer': {'name': (self.company_id.name or '')[:200], 'tax_id': (self.company_id.vat or '')[:60], 'email': (self.company_id.email or '')[:200],
                       'address': ', '.join(p for p in [self.company_id.street, self.company_id.zip, self.company_id.city, self.company_id.country_id.name] if p)[:500]},
            'currency': currency.name, 'lines': lines, 'external_ref': ('odoo:%s' % self.name)[:100],
            'number': re.sub(r'[^\w/.-]', '', self.name or '')[:40],
        }
        if self.invoice_date:
            payload['issue_date'] = fields.Date.to_string(self.invoice_date)
        if self.invoice_date_due and (not self.invoice_date or self.invoice_date_due >= self.invoice_date):
            payload['due_date'] = fields.Date.to_string(self.invoice_date_due)
        if self.partner_id.lang:
            payload['lang'] = self.partner_id.lang.split('_')[0]
        return payload

    def action_blokbay_invoice(self):
        """ Button "Pay with Blokbay": creates the Blokbay invoice (no email from Blokbay: Odoo sends its own invoice email, with the link). """
        for move in self:
            if not move._blokbay_can_pay():
                raise UserError(_("Only posted customer invoices that are not paid yet can be paid with Blokbay."))
            provider = move._blokbay_provider()
            payload = move._blokbay_invoice_payload()
            key = 'odoo-invoice:%s:%s:%s' % (move.id, move.name, move.blokbay_attempt + 1)
            try:
                data = provider._blokbay_request('POST', '/api/v1/invoices', payload=payload, idempotency_key=key)
            except ValidationError as e:
                if 'number' not in str(e):
                    raise
                # The number is already used by another Blokbay invoice (e.g. a cancelled one): Blokbay numbers this one.
                payload = {k: v for k, v in payload.items() if k != 'number'}
                data = provider._blokbay_request('POST', '/api/v1/invoices', payload=payload, idempotency_key=key + ':auto')
            if not INVOICE_ID_RE.match(data.get('id') or '') or not PAY_URL_RE.match(data.get('url') or ''):
                raise ValidationError("Blokbay: " + _("Unexpected answer from the API."))
            move.write({'blokbay_invoice_id': data['id'], 'blokbay_payment_url': data['url'], 'blokbay_invoice_status': 'open', 'blokbay_attempt': move.blokbay_attempt + 1})
            move.message_post(body=_("Blokbay payment link created: %(url)s (invoice %(number)s, USDC or USDT).", url=data['url'], number=data.get('number') or ''))
        return True

    def _blokbay_apply_invoice(self, provider, data):
        """ Invoice event from the webhook (already read again from the API): paid registers the payment, void cancels the link. """
        self.ensure_one()
        status = data.get('status')
        if status == 'paid' and self.blokbay_invoice_status != 'paid':
            self.blokbay_invoice_status = 'paid'
            pay = data.get('payment') or {}
            self.message_post(body=_("Paid with Blokbay: %(amount)s %(currency)s in %(coin)s on %(network)s, transaction %(tx)s.",
                                     amount=data.get('total'), currency=data.get('currency'), coin=pay.get('coin') or '', network=pay.get('network') or '', tx=pay.get('tx') or ''))
            self._blokbay_register_payment(provider, data)
            return 'paid'
        if status == 'void' and self.blokbay_invoice_status == 'open':
            self.write({'blokbay_invoice_status': 'void', 'blokbay_payment_url': False})
            self.message_post(body=_("The Blokbay payment link was cancelled."))
            return 'void'
        return 'duplicate'

    def _blokbay_register_payment(self, provider, data):
        if self.payment_state in ('paid', 'in_payment') or self.currency_id.is_zero(self.amount_residual):
            return
        if (data.get('currency') or '') != self.currency_id.name:
            return
        journal = provider.journal_id if 'journal_id' in provider._fields and provider.journal_id else self.env['account.journal'].search(
            [('type', '=', 'bank'), ('company_id', '=', self.company_id.id)], limit=1)
        if not journal:
            self.message_post(body=_("Register the payment by hand: no bank journal found for Blokbay."))
            return
        paid_at = ((data.get('payment') or {}).get('paid_at') or data.get('paid_at') or '')[:10]
        wizard = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=self.ids).create({
            'journal_id': journal.id, 'amount': self.amount_residual,
            'payment_date': fields.Date.from_string(paid_at) if paid_at else fields.Date.context_today(self),
            'communication': 'Blokbay %s' % (data.get('number') or self.name),
        })
        wizard._create_payments()


# account.move.send is a wizard (TransientModel) in Odoo 17 and an AbstractModel in Odoo 18.
_SEND_BASE = models.TransientModel if release.version_info[0] < 18 else models.AbstractModel


class AccountMoveSend(_SEND_BASE):
    _inherit = 'account.move.send'

    def _get_default_mail_body(self, move, mail_template, mail_lang):
        body = super()._get_default_mail_body(move, mail_template, mail_lang)
        if move.blokbay_payment_url and move.blokbay_invoice_status == 'open':
            body = Markup(body or '') + Markup('<p>%s <a href="%s">%s</a></p>') % (escape(_("Pay in USDC or USDT:")), escape(move.blokbay_payment_url), escape(move.blokbay_payment_url))
        return body
