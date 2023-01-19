{
    'name': "Binaural contactos",

    'summary': """
       Modulo para información de contacto """,

    'license': 'LGPL-3',

    'description': """
        - Modelo de tipo de persona
    """,
    
    'author': "Binauraldev",
    'website': "https://binauraldev.com/",
    'category': 'Contacts/Contacts',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': ['base','contacts'],

    # always loaded
    'data': [
        'views/res_partner.xml',
    ],

    'application':True,
}