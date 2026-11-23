# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
import hashlib
import hmac
import logging
import re
import time

import requests

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_blokbay import const

_logger = logging.getLogger(__name__)

PAYMENT_ID_RE = re.compile(r'^gp_[a-z0-9]{6,40}$')


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(selection_add=[('blokbay', "Blokbay")], ondelete={'blokbay': 'set default'})
    blokbay_public_key = fields.Char(
        string="Blokbay Public Key",
        help="pk_live_... from Blokbay > Payments from your site. Webhooks of other accounts are refused.",
        required_if_provider='blokbay',
    )
    blokbay_secret_key = fields.Char(
        string="Blokbay Secret Key", help="sk_live_... shown once in your Blokbay dashboard.",
        required_if_provider='blokbay', groups='base.group_system',
    )
    blokbay_webhook_secret = fields.Char(
        string="Blokbay Webhook Signing Secret", help="whsec_... from Blokbay > Payments from your site > Webhook.",
        required_if_provider='blokbay', groups='base.group_system',
    )
    blokbay_api_url = fields.Char(
        string="Blokbay API URL", default=const.DEFAULT_API_URL, groups='base.group_system',
        help="Leave the default value. Change it only for a local test server.",
    )
    blokbay_webhook_url = fields.Char(string="Webhook URL", compute='_compute_blokbay_webhook_url')
    blokbay_currency_warning = fields.Char(string="Blokbay Currency Notice", compute='_compute_blokbay_currency_warning')

    @api.depends('code', 'company_id.currency_id')
    def _compute_blokbay_currency_warning(self):
        for provider in self:
            cur = provider.company_id.currency_id.name if provider.company_id else False
            provider.blokbay_currency_warning = _(
                "Blokbay accepts prices in %(accepted)s. The currency of this company is %(currency)s: the crypto payment "
                "method stays hidden for payments in that currency.",
                accepted=', '.join(const.SUPPORTED_CURRENCIES), currency=cur,
            ) if provider.code == 'blokbay' and cur and cur not in const.SUPPORTED_CURRENCIES else False

    @api.depends('code')
    def _compute_blokbay_webhook_url(self):
        for provider in self:
            provider.blokbay_webhook_url = (
                provider.get_base_url().rstrip('/') + '/payment/blokbay/webhook' if provider.code == 'blokbay' else False
            )

    @api.constrains('blokbay_api_url')
    def _check_blokbay_api_url(self):
        for provider in self.sudo():
            url = (provider.blokbay_api_url or '').strip()
            if url and not re.match(r'^https?://[^\s/]+', url):
                raise ValidationError(_("The Blokbay API URL must start with https://"))

    # === BUSINESS METHODS === #

    @api.model
    def _get_compatible_providers(self, *args, is_validation=False, report=None, **kwargs):
        """ Blokbay cannot be used to save a payment method (validation operations). """
        providers = super()._get_compatible_providers(*args, is_validation=is_validation, report=report, **kwargs)
        if is_validation:
            unfiltered = providers
            providers = providers.filtered(lambda p: p.code != 'blokbay')
            payment_utils.add_to_report(report, unfiltered - providers, available=False, reason=_("Validation is not supported."))
        return providers

    def _get_supported_currencies(self):
        supported = super()._get_supported_currencies()
        if self.code == 'blokbay':
            supported = supported.filtered(lambda c: c.name in const.SUPPORTED_CURRENCIES)
        return supported

    def _get_default_payment_method_codes(self):
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'blokbay':
            return default_codes
        return const.DEFAULT_PAYMENT_METHOD_CODES

    def _blokbay_request(self, method, path, payload=None, idempotency_key=None):
        """ Call the Blokbay gateway API from the server (never from the browser: the API refuses browser origins).

        :return: the JSON response
        :raise ValidationError: on network errors and non-2xx answers
        """
        self.ensure_one()
        base = (self.sudo().blokbay_api_url or const.DEFAULT_API_URL).rstrip('/')
        headers = {
            'Authorization': f'Bearer {(self.sudo().blokbay_secret_key or "").strip()}',
            'Accept': 'application/json',
            'User-Agent': 'Blokbay-Odoo/1.0',
        }
        if idempotency_key:
            headers['Idempotency-Key'] = str(idempotency_key)[:100]
        try:
            response = requests.request(method, base + path, json=payload, headers=headers, timeout=20, allow_redirects=False)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _logger.exception("Blokbay: unable to reach %s", base + path)
            raise ValidationError("Blokbay: " + _("Could not establish the connection to the API."))
        try:
            data = response.json()
        except ValueError:
            data = {}
        if not 200 <= response.status_code < 300:
            _logger.warning("Blokbay: API error %s on %s %s: %s", response.status_code, method, path, data.get('error'))
            raise ValidationError("Blokbay: " + _(
                "The communication with the API failed. Blokbay gave us the following information: %s",
                data.get('message') or data.get('error') or response.status_code,
            ))
        return data

    def _blokbay_get_payment(self, payment_id):
        self.ensure_one()
        if not PAYMENT_ID_RE.match(payment_id or ''):
            raise ValidationError("Blokbay: " + _("Invalid payment id."))
        return self._blokbay_request('GET', f'/api/v1/payments/{payment_id}')

    def _blokbay_verify_signature(self, raw_body, header, now=None):
        """ Blokbay-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<raw body>" with the signing secret>. """
        self.ensure_one()
        secret = (self.sudo().blokbay_webhook_secret or '').strip()
        if not secret or not header:
            return False
        parts = {}
        for item in str(header).split(','):
            key, sep, value = item.strip().partition('=')
            if sep:
                parts[key] = value
        ts, sig = parts.get('t', ''), parts.get('v1', '')
        if not ts.isdigit() or not sig:
            return False
        if abs((now or time.time()) - int(ts)) > const.SIGNATURE_TOLERANCE:
            return False
        if isinstance(raw_body, str):
            raw_body = raw_body.encode()
        expected = hmac.new(secret.encode(), ts.encode() + b'.' + raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig)
