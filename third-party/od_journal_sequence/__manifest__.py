# -*- coding: utf-8 -*-

{
    'name': 'Journal Sequence For Odoo 16',
    'version': '16.0.1.0.1',
    'category': 'Accounting',
    'summary': 'Odoo Journal Sequence, Journal Entry Sequence, Odoo 16 Journal Sequence, Journal Sequence For Odoo 16, Journal Sequence For Invoice',
    'description': 'Odoo Journal Sequence, Journal Entry Sequence, Odoo 16 Journal Sequence, Journal Sequence For Odoo 16, Journal Sequence For Invoice',
    'sequence': '1',
    'author': 'Odoo Developers',
    'support': 'developersodoo@gmail.com',
    'live_test_url': 'https://www.youtube.com/watch?v=z-xZwCah7wM',
    'depends': ['account'],
    'demo': [],
    'data': [
        'security/ir.model.access.csv',
        'views/account_journal.xml',
        'views/account_move.xml',
    ],
    'license': 'OPL-1',
    'price': 8,
    'currency': 'USD',
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': "create_journal_sequences",
    'images': ['static/description/banner.png'],
}
