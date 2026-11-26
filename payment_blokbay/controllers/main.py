# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
import json
import logging
import re

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)

INVOICE_ID_RE = re.compile(r'^inv_[a-z0-9]{6,40}$')


class BlokbayController(http.Controller):
    _return_url = '/payment/blokbay/return'
    _cancel_url = '/payment/blokbay/cancel'
    _webhook_url = '/payment/blokbay/webhook'

    def _process_return(self, ref, cancel=False):
        if ref:
            try:
                data = {'reference': ref}
                if cancel:
                    data['blokbay_cancel'] = True
                request.env['payment.transaction'].sudo()._handle_notification_data('blokbay', data)
            except ValidationError:
                _logger.exception("Blokbay: unable to process the return for %s", ref)
        return request.redirect('/payment/status')

    @http.route(_return_url, type='http', methods=['GET'], auth='public', save_session=False)
    def blokbay_return(self, ref=None, **kwargs):
        """ The buyer comes back from the Blokbay page after paying: the payment is checked with the API at once,
        so the order is confirmed even if the webhook has not arrived yet. """
        return self._process_return(ref)

    @http.route(_cancel_url, type='http', methods=['GET'], auth='public', save_session=False)
    def blokbay_cancel(self, ref=None, **kwargs):
        return self._process_return(ref, cancel=True)

    @http.route(_webhook_url, type='http', methods=['POST'], auth='public', csrf=False, save_session=False)
    def blokbay_webhook(self):
        """ Signed webhook (payment.paid, payment.expired, ping). The signature is checked against every enabled Blokbay
        provider (one per company), then the payment is read again from the API before the transaction changes. """
        raw = request.httprequest.get_data()
        header = request.httprequest.headers.get('Blokbay-Signature', '')
        providers = request.env['payment.provider'].sudo().search([('code', '=', 'blokbay'), ('state', '!=', 'disabled')])
        provider = next((p for p in providers if p._blokbay_verify_signature(raw, header)), None)
        if not provider:
            _logger.warning("Blokbay: webhook with an invalid signature")
            return request.make_response('bad signature', headers=[('Content-Type', 'text/plain')], status=400)
        try:
            event = json.loads(raw)
        except ValueError:
            return request.make_response('bad payload', headers=[('Content-Type', 'text/plain')], status=400)
        if not isinstance(event, dict) or not isinstance(event.get('type'), str):
            return request.make_response('bad payload', headers=[('Content-Type', 'text/plain')], status=400)
        if provider.blokbay_public_key and event.get('account') != provider.blokbay_public_key.strip():
            return request.make_response('other account', headers=[('Content-Type', 'text/plain')], status=400)
        if event['type'] == 'ping':
            return request.make_response('pong', headers=[('Content-Type', 'text/plain')])
        data = event.get('data') or {}
        if event['type'].startswith('invoice.'):
            return self._blokbay_invoice_event(provider, data)
        tx = request.env['payment.transaction'].sudo().search([
            ('provider_id', '=', provider.id), ('provider_reference', '=', data.get('id') or '-'),
        ], limit=1)
        if not tx:
            return request.make_response('unknown payment', headers=[('Content-Type', 'text/plain')])
        state_before = tx.state
        try:
            tx._handle_notification_data('blokbay', {'reference': tx.reference, 'id': data.get('id')})
        except ValidationError:
            _logger.exception("Blokbay: unable to process the webhook for %s", tx.reference)
            # API unreachable or refused: answer 503 so Blokbay delivers the event again later.
            return request.make_response('retry', headers=[('Content-Type', 'text/plain')], status=503)
        msg = 'duplicate' if state_before == tx.state and tx.state in ('done', 'cancel') else tx.state
        return request.make_response(msg, headers=[('Content-Type', 'text/plain')])

    def _blokbay_invoice_event(self, provider, data):
        """ invoice.paid / invoice.voided / invoice.overdue for an invoice created with "Pay with Blokbay": the invoice is read again
        from the API (never trusted from the webhook body) before the Odoo invoice changes. """
        text = lambda msg, status=200: request.make_response(msg, headers=[('Content-Type', 'text/plain')], status=status)
        inv_id = data.get('id') or ''
        if not INVOICE_ID_RE.match(inv_id):
            return text('unknown invoice')
        move = request.env['account.move'].sudo().search([('blokbay_invoice_id', '=', inv_id), ('company_id', '=', provider.company_id.id)], limit=1)
        if not move:
            return text('unknown invoice')
        try:
            fresh = provider._blokbay_request('GET', f'/api/v1/invoices/{inv_id}')
        except ValidationError:
            _logger.exception("Blokbay: unable to read the invoice %s", inv_id)
            return text('retry', 503)
        if fresh.get('id') != inv_id:
            return text('unknown invoice')
        return text(move._blokbay_apply_invoice(provider, fresh))
