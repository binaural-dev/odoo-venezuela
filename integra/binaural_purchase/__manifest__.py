{
    'name': "Binaural Compras",

    'summary': """
       Modulo para compras """,

    'license': 'LGPL-3',
    
    'author': "Binauraldev",
    'website': "https://binauraldev.com/",
    'category': 'Purchase/Purchase',
    'version': '16.0',

    # any module necessary for this one to work correctly
    'depends': ['base', 'purchase', 'binaural_tax', 'binaural_rate'],

    # always loaded
    'data': [
        'views/purchase_order.xml',
        
    ],

    'images': ['static/description/icon.png'],

    'application':True,
}
