# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': "Crypto Payments (USDT, USDC, ETH, BTC, SOL) - Blokbay",
    'version': '17.0.1.2.0',
    'category': 'Accounting/Payment Providers',
    'sequence': 350,
    'summary': "Accept crypto payments in Odoo eCommerce: USDT, USDC, ETH, BTC and SOL, paid straight to your own wallet. 1% per payment.",
    'description': " ",  # Non-empty string to avoid loading the README file; the Apps Store page is static/description/index.html.
    'author': "Blokbay",
    'website': "https://blokbay.com",
    'support': "mail@blokbay.com",
    'depends': ['payment'],
    'data': [
        'views/payment_blokbay_templates.xml',
        'views/payment_provider_views.xml',
        'views/payment_transaction_views.xml',
        'data/payment_method_data.xml',
        'data/payment_method_currencies.xml',
        'data/payment_provider_data.xml',
    ],
    'images': ['static/description/banner.png'],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
