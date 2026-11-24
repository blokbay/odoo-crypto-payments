========================
Blokbay Crypto Payments
========================

Accept USDT, USDC, ETH, BTC and SOL, paid from a wallet or an exchange. No custody: funds go straight from the buyer to your wallet.
Blokbay keeps 1% of the amount paid, with no fixed costs.

Setup
=====

1. Open a free account at https://blokbay.com and add your wallet.
2. In Blokbay, open *Payments from your site* and copy the public key, the secret key and the webhook signing secret.
3. In Odoo, open *Website > Configuration > Payment Providers > Blokbay* (or *Invoicing > Configuration > Payment Providers*),
   paste the three values, copy the *Webhook URL* shown there into Blokbay, and set the state to *Enabled*.

How it works
============

* At checkout the buyer chooses *Crypto (USDT, USDC, ETH, BTC, SOL)* (installations made before 1.2.0 keep the name
  *Crypto (BTC, USDC, USDT, ETH)* or the one you set) and is redirected to the Blokbay payment page.
* On that page the buyer chooses coin and network (and can change them before paying), then pays from a connected wallet,
  or by address and QR code from any wallet or exchange. Coins: USDT and USDC on Ethereum, BNB Smart Chain, Arbitrum,
  Polygon and Solana; USDC on Base; ETH on Ethereum, Base and Arbitrum; SOL on Solana; Bitcoin.
* The payment state is always read from the Blokbay API: paid = done, expired = cancelled. A payment confirmed after the expiry
  is still recorded, because the funds already reached your wallet.
* The signed webhook updates the transaction even if the buyer closes the page. The return page checks the payment at once.
* Network, coin and blockchain transaction are shown on the payment transaction.

Notes
=====

* Currencies: USD, EUR, GBP, CHF, JPY, CAD, AUD, SGD, HKD, AED; the buyer pays in crypto at the current exchange rate.
  Minimum: the equivalent of 1.00 USD (Bitcoin from the equivalent of 100 USD).
* Refunds are sent by you from your wallet; the module does not process them.
* You stay responsible for your shop and for your obligations to your customers.
* Support: mail@blokbay.com

Changelog
=========

* 1.2.0: updated texts (USDT, USDC, ETH, BTC and SOL; payment from a wallet or an exchange). No change to how the module works.
* 1.1.0: currencies USD, EUR, GBP, CHF, JPY, CAD, AUD, SGD, HKD and AED.
