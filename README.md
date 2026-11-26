# Blokbay crypto payments for Odoo

Non-custodial crypto payment provider for Odoo eCommerce: USDT, USDC, ETH, BTC and SOL paid straight to the merchant wallet, from a wallet or an exchange.
Module: payment_blokbay. Docs: https://blokbay.com/docs/api

## Crypto invoices in USDC and USDT (version 1.3.0)

The module also adds a **Pay with Blokbay** button to posted customer invoices: it creates a stablecoin invoice with the same customer,
lines and taxes, puts the USDC or USDT payment link on the invoice, in the PDF and in the invoice email, and registers the payment in
Odoo when the signed `invoice.paid` webhook arrives (the invoice is read again from the Blokbay API first). Funds go straight to your
wallet: Blokbay is non-custodial. More: https://blokbay.com/stablecoin-invoices/odoo
