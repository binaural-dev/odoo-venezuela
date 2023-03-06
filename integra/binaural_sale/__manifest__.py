{
    'name': "Binaural Ventas",

    'summary': """
       Modulo para ventas """,

    'license': 'LGPL-3',
    
    'author': "Binauraldev",
    'website': "https://binauraldev.com/",
    'category': 'Sales/Sales',
    'version': '16.0',

    # any module necessary for this one to work correctly
    'depends': ['base', 'binaural_tax','sale_management', 'binaural_rate', 'binaural_contact'],

    # always loaded
    'data': [
        'views/sale_order.xml'
    ],

    'images': ['static/description/icon.png'],

    'application':True,
}
