========================
Blokbay Crypto Payments
========================

Accept BTC, USDC, USDT and ETH. No custody: funds go from the buyer's wallet to yours in the same transaction.
Blokbay keeps 1% of the amount paid, with no fixed costs.

Setup
=====

1. Open a free account at https://blokbay.com and add your wallet.
2. In Blokbay, open *Payments from your site* and copy the public key, the secret key and the webhook signing secret.
3. In Odoo, open *Website > Configuration > Payment Providers > Blokbay* (or *Invoicing > Configuration > Payment Providers*),
   paste the three values, copy the *Webhook URL* shown there into Blokbay, and set the state to *Enabled*.

How it works
============

* At checkout the buyer chooses *Crypto (BTC, USDC, USDT, ETH)* and is redirected to the Blokbay payment page.
* The payment state is always read from the Blokbay API: paid = done, expired = cancelled. A payment confirmed after the expiry
  is still recorded, because the funds already reached your wallet.
* The signed webhook updates the transaction even if the buyer closes the page. The return page checks the payment at once.
* Network, coin and blockchain transaction are shown on the payment transaction.

Notes
=====

* Currency: USD. Minimum 1.00 USD (Bitcoin from 100 USD).
* Refunds are sent by you from your wallet; the module does not process them.
* You stay responsible for your shop and for your obligations to your customers.
* Support: mail@blokbay.com
