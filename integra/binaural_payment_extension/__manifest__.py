{
    'name': "Binaural Retenciones",

    'summary': """
       Modulo de extensiones de pago """,

    'license': 'LGPL-3',
    
    'author': "Binauraldev",
    'website': "https://binauraldev.com/",
    'category': 'Accountant/Accountant',
    'version': '16.0',

    # any module necessary for this one to work correctly
    'depends': ['base', 'binaural_rate', 'account_accountant', 'binaural_location', 'binaural_fiscal'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/ir_sequence.xml',
        'views/tax_unit.xml',
        'views/fees_retention.xml',
        'views/economic_activity.xml',
        'views/economic_branch.xml',
        'views/payment_concept.xml',
        'views/signature_config.xml',
        'views/type_withholding.xml',
        'views/account_retention_line.xml',
        'views/account_retention_iva.xml',
        'views/account_retention_islr.xml',
        'views/account_payment.xml',
        'wizard/account_payment_register.xml',
        'views/menu.xml',
        ],

    'images': ['static/description/icon.png'],

    'application':True,
}
