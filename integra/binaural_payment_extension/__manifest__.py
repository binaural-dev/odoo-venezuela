{
    'name': "Binaural Extensiones de pago",

    'summary': """
       Modulo de extensiones de pago """,

    'license': 'LGPL-3',
    
    'author': "Binauraldev",
    'website': "https://binauraldev.com/",
    'category': 'Accountant/Accountant',
    'version': '16.0',

    # any module necessary for this one to work correctly
    'depends': ['base', 'binaural_rate', 'account_accountant', 'binaural_location'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/menu.xml',
        'views/tax_unit.xml',
        'views/fees_retention.xml',
        'views/economic_activity.xml',
        'views/economic_branch.xml',
        'views/payment_concept.xml',
        'views/signature_config.xml',
        'views/type_withholding.xml'
        ],

    'images': ['static/description/icon.png'],

    'application':True,
}