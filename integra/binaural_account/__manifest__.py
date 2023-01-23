{
    'name': "Contabilidad - Venezolana",

    'summary': """
       Modulo para contabilidad Venezolana """,

    'license': 'LGPL-3',
    
    'author': "Binauraldev",
    'website': "https://binauraldev.com/",
    'category': 'Accounting/Localizations/Account Chart',

    # any module necessary for this one to work correctly
    'depends': ['base','account'],

    # always loaded
    'data': [
        'data/account_data.xml',
        'views/res_config_settings.xml',
    ],

    'images': ['static/description/icon.png'],

    'application':True,
}