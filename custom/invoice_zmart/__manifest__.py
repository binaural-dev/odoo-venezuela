{
    'name': "Zmart Invoice",

    'summary': """
       Modulo para personalizar el modulos de 
       contabilidad con nuevos campos""",
    'license': 'LGPL-3',
    'author': "Binauraldev",
    'website': "https://binauraldev.com/",
    'category': 'Invoice',
    'version': '16.0',
    'depends': ['binaural_invoice'],
    'data': [
        # 'security/ir.model.access.csv',
        'views/account_move.xml',
        'views/account_payment.xml',
    ],
    'images': ['static/description/icon.png'],
    'application':True,
}