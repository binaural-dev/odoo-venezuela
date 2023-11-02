{
    'name': "Zmart contactos",

    'summary': """
       Modulo para agregar campos en el modulo de contacto """,
    'license': 'LGPL-3',
    'author': "Binauraldev",
    'website': "https://binauraldev.com/",
    'category': 'Contacts/Contacts',
    'version': '16.1',
    'depends': ['binaural_contact', 'binaural_payment_extension', 'binaural_tax_payer'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner.xml',
        'views/res_company.xml',
    ],
    'images': ['static/description/icon.png'],
    'application':True,
}