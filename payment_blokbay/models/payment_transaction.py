# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
import logging

from werkzeug import urls

from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, float_round

from odoo.addons.payment_blokbay import const

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    blokbay_tx_hash = fields.Char(string="Blockchain Transaction", readonly=True, copy=False)
    blokbay_network = fields.Char(string="Network", readonly=True, copy=False)
    blokbay_coin = fields.Char(string="Coin", readonly=True, copy=False)

    def _get_specific_rendering_values(self, processing_values):
        """ Create the Blokbay payment and return the URL of its payment page for the redirect form. """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'blokbay':
            return res
        currency = self.currency_id.name
        if currency not in const.SUPPORTED_CURRENCIES:
            raise ValidationError("Blokbay: " + _("Payments in %s are not supported.", currency))
        digits = const.CURRENCY_DECIMALS[currency]
        amount = float_round(self.amount, precision_digits=digits)
        if currency == 'USD' and amount < const.MIN_AMOUNT:
            raise ValidationError("Blokbay: " + _("The minimum amount is 1.00 USD."))
        base_url = self.provider_id.get_base_url()
        ref_q = urls.url_encode({'ref': self.reference})
        payload = {
            'amount': '%.*f' % (digits, amount),
            'currency': currency,
            'reference': self.reference[:100],
            'description': (_("Order %s", self.reference) + (' - ' + self.company_id.name if self.company_id.name else ''))[:200],
            'url_success': urls.url_join(base_url, '/payment/blokbay/return') + '?' + ref_q,
            'url_cancel': urls.url_join(base_url, '/payment/blokbay/cancel') + '?' + ref_q,
        }
        if self.partner_email:
            payload['customer_email'] = self.partner_email
        payment = self.provider_id._blokbay_request('POST', '/api/v1/payments', payload, idempotency_key='odoo:' + self.reference + ('' if currency == 'USD' else ':' + currency))
        self.provider_reference = payment.get('id')
        return {'api_url': payment['url']}

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'blokbay' or len(tx) == 1:
            return tx
        reference = notification_data.get('reference')
        payment_id = notification_data.get('id')
        domain = [('provider_code', '=', 'blokbay')]
        if reference:
            domain.append(('reference', '=', reference))
        elif payment_id:
            domain.append(('provider_reference', '=', payment_id))
        else:
            raise ValidationError("Blokbay: " + _("Received data with missing reference."))
        tx = self.search(domain, limit=1)
        if not tx:
            raise ValidationError("Blokbay: " + _("No transaction found matching reference %s.", reference or payment_id))
        return tx

    def _process_notification_data(self, notification_data):
        """ Always read the payment from the Blokbay API: the state never depends on data sent by the browser. """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'blokbay':
            return
        if not self.provider_reference:
            raise ValidationError("Blokbay: " + _("The transaction has no Blokbay payment."))
        payment = self.provider_id._blokbay_get_payment(self.provider_reference)
        if payment.get('id') != self.provider_reference or payment.get('reference') != self.reference[:100]:
            raise ValidationError("Blokbay: " + _("The payment does not match the transaction."))
        status = payment.get('status')
        if status == const.STATUS_PAID:
            amount = float(payment.get('amount') or 0)
            currency = self.currency_id.name
            digits = const.CURRENCY_DECIMALS.get(currency, 2)
            if payment.get('currency') != currency or float_compare(amount, self.amount, precision_digits=digits) != 0:
                _logger.warning("Blokbay: amount mismatch for %s: %s %s", self.reference, payment.get('amount'), payment.get('currency'))
                self._set_error("Blokbay: " + _("The amount paid does not match the transaction amount."))
                return
            self.write({
                'blokbay_tx_hash': payment.get('tx') or False,
                'blokbay_network': payment.get('network') or False,
                'blokbay_coin': payment.get('coin') or False,
            })
            # A payment confirmed after the expiry (or after the buyer pressed cancel) is still valid: the funds already
            # reached the merchant's wallet, so a canceled transaction can become done.
            self._set_done(extra_allowed_states=('cancel',))
        elif status == const.STATUS_EXPIRED:
            self._set_canceled(state_message=_("The crypto payment expired."))
        elif status == const.STATUS_PENDING:
            if notification_data.get('blokbay_cancel'):
                self._set_canceled(state_message=_("The customer left the crypto payment page."))
            else:
                self._set_pending()
        else:
            _logger.warning("Blokbay: unknown status %s for %s", status, self.reference)
            self._set_error("Blokbay: " + _("Unknown payment status: %s", status))
