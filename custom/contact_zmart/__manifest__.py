{
    'name': "Zmart contactos",

    'summary': """
       Modulo para agregar campos en el modulo de contacto """,
    'license': 'LGPL-3',
    'author': "Binauraldev",
    'website': "https://binauraldev.com/",
    'category': 'Contacts/Contacts',
    'version': '16.0',
    'depends': ['binaural_contact'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner.xml',
    ],
    'images': ['static/description/icon.png'],
    'application':True,
}