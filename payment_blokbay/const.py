# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

DEFAULT_API_URL = 'https://blokbay.com'

# Currencies accepted by the Blokbay gateway API, with their decimals (JPY has none). The buyer pays in crypto at the current
# exchange rate; amount and currency come back in the payment and in webhooks exactly as sent. Minimum: the equivalent of
# 1.00 USD, checked by Blokbay at the exchange rate (checked here only for USD).
CURRENCY_DECIMALS = {'USD': 2, 'EUR': 2, 'GBP': 2, 'CHF': 2, 'JPY': 0, 'CAD': 2, 'AUD': 2, 'SGD': 2, 'HKD': 2, 'AED': 2}
SUPPORTED_CURRENCIES = list(CURRENCY_DECIMALS)
MIN_AMOUNT = 1.0

# Payment method activated with the provider.
DEFAULT_PAYMENT_METHOD_CODES = {'blokbay_crypto'}

# Blokbay payment statuses (GET /api/v1/payments/<id>).
STATUS_PENDING = 'pending'
STATUS_PAID = 'paid'
STATUS_EXPIRED = 'expired'

# Webhook signature: Blokbay-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<raw body>">.
SIGNATURE_TOLERANCE = 300
