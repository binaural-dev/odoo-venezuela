{
    'name': "Zmart products",

    'summary': """
       Modulo para personalizar la ficha del producto""",
    'license': 'LGPL-3',
    'author': "Binauraldev",
    'website': "https://binauraldev.com/",
    'category': 'Products',
    'version': '16.0',
    'depends': ['binaural_stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_template.xml',
    ],
    'images': ['static/description/icon.png'],
    'application':True,
}