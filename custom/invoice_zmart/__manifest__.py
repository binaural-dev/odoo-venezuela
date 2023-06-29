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
        'data/res_group.xml',
        'security/ir.model.access.csv',
        'report/delivery_note_bs.xml',
        'report/delivery_note_usd.xml',
        'views/account_move.xml',
        'views/account_payment.xml',
        'report/free_form_bs.xml',
    ],
    'images': ['static/description/icon.png'],
    'application':True,
}