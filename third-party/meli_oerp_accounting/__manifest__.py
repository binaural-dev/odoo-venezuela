{
    "name": "MercadoLibre Accounting / Mercado Libre Publisher Extension",
    'version': "17.0.1.0.0",
    'author': 'Moldeo Interactive',
    'website': 'https://www.moldeointeractive.com',
    'category': 'Sale',
    'sequence': 14,
    'summary': 'MercadoLibre Accounting / Mercado Libre Publisher Extension',
    'depends': [
        'base',
        'account',
        'sale',
        'meli_oerp'
    ],
    'external_dependencies': {},
    'data': [
        'data/account_data.xml',
        'security/ir.model.access.csv',
        'views/meli_view.xml',
        'views/company_view.xml',
        #'wizard/mercadolibre_public_invoice.xml'
    ],
    'demo': [
    ],
    'price': '100.00',
    'currency': 'USD',
    "external_dependencies": {"python": ['pdf2image','meli']},
    'images': [ 'static/description/main_screenshot.png',
                'static/description/meli_oerp_accounting_configuration.png',
                'static/description/moldeo_interactive_logo.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'GPL-3',
}
