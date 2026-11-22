# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

DEFAULT_API_URL = 'https://blokbay.com'

# The Blokbay gateway API works in USD (amount with 2 decimals, from 1.00).
SUPPORTED_CURRENCIES = ['USD']
MIN_AMOUNT = 1.0

# Payment method activated with the provider.
DEFAULT_PAYMENT_METHOD_CODES = {'blokbay_crypto'}

# Blokbay payment statuses (GET /api/v1/payments/<id>).
STATUS_PENDING = 'pending'
STATUS_PAID = 'paid'
STATUS_EXPIRED = 'expired'

# Webhook signature: Blokbay-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<raw body>">.
SIGNATURE_TOLERANCE = 300
