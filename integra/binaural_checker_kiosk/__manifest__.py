{
    'name': "Binaural Kiosko",

    'summary': """
       Modulo para personalizaciones del modulo Product Price Checker""",

    'license': 'LGPL-3',
    
    'author': "Binauraldev",
    'website': "https://binauraldev.com/",
    'category': 'Extra Tools',
    'version': '1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['sh_price_checker_kiosk'],

    # always loaded
    'data': [
        'data/res_user_data.xml',
        'data/res_company_data.xml'
    ],

    "assets": {
        'web.assets_backend': [
            'binaural_checker_kiosk/static/src/js/kiosk_mode.js',
            'binaural_checker_kiosk/static/src/xml/*.xml'
        ]
    },
    
    'images': ['static/description/icon.png'],

    'application':True,
    "binaural":True,
}
