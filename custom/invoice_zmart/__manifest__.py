{
    'name': "Zmart Invoice",

    'summary': """
       Modulo para personalizar el modulos de 
       contabilidad con nuevos campos""",
    'license': 'LGPL-3',
    'author': "Binauraldev",
    'website': "https://binauraldev.com/",
    'category': 'Invoice',
    'version': '16.0.1.9',
    'depends': ['binaural_invoice', 'binaural_base_igtf'],
    'data': [
        'data/paperformat.xml',
        'data/res_group.xml',
        'security/ir.model.access.csv',
        'report/delivery_note_bs.xml',
        'report/delivery_note_usd.xml',
        'report/digital_invoice.xml',
        'report/free_form_bs.xml',
        'report/free_form_usd.xml',
        'views/account_move.xml',
        'views/account_payment.xml',
        'wizard/wizard_confirm_account_move_view.xml',
        
    ],
    'images': ['static/description/icon.png'],
    'application':True,
}
