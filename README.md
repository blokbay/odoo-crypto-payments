# Odoo 17 and 18 Crypto Payment Gateway: Bitcoin, USDT, USDC, ETH (Blokbay)

Accept crypto payments in Odoo 17 and 18: Bitcoin (BTC), Tether (USDT), USD Coin (USDC) and Ether (ETH) on Ethereum, BNB Smart Chain (BSC), Polygon, Base and Arbitrum. Non-custodial: every payment goes straight to your own wallet. 1% per payment, no monthly fee. Download the latest release: [Releases](../../releases/latest).

Non-custodial crypto payment provider for Odoo eCommerce: USDT, USDC, ETH, BTC and SOL paid straight to the merchant wallet, from a wallet or an exchange.
Module: payment_blokbay. Docs: https://blokbay.com/docs/api

## Supported networks
Payments settle on chain through the verified LuxSplit gateway contract `0xd4b637cC81D5B5115Cd0204A9ba6B60474F05e31` (same address on every network, source verified on Sourcify):

| Network | Chain ID | Assets |
|---|---|---|
| BNB Smart Chain (BSC, BNB Chain) | 56 | USDC, USDT |
| Ethereum | 1 | ETH, USDC, USDT |
| Polygon | 137 | USDC, USDT |
| Base | 8453 | USDC |
| Arbitrum | 42161 | USDC, USDT |
| Bitcoin | – | BTC (orders from 100 USD) |

On BNB Smart Chain the buyer pays with USDC or USDT (BEP-20) and the funds reach the merchant's wallet in the same transaction.
Verified source (Sourcify, chain 56): https://repo.sourcify.dev/56/0xd4b637cC81D5B5115Cd0204A9ba6B60474F05e31
The network list is also in [`networks.json`](networks.json).


## Crypto invoices in USDC and USDT (version 1.3.0)

The module also adds a **Pay with Blokbay** button to posted customer invoices: it creates a stablecoin invoice with the same customer,
lines and taxes, puts the USDC or USDT payment link on the invoice, in the PDF and in the invoice email, and registers the payment in
Odoo when the signed `invoice.paid` webhook arrives (the invoice is read again from the Blokbay API first). Funds go straight to your
wallet: Blokbay is non-custodial. More: https://blokbay.com/stablecoin-invoices/odoo
