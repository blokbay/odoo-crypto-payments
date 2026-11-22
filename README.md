# Blokbay crypto payments for Odoo

Non-custodial crypto payment provider for Odoo eCommerce: Bitcoin, USDC, USDT and ETH paid straight to the merchant wallet.
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

