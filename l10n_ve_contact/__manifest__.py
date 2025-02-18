{
    "name": "Binaural contactos",
    "summary": """
       Modulo para información de contacto """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Contacts/Contacts",
    "version": "17.0.1.0.2",
    # any module necessary for this one to work correctly
    'depends': ['base','contacts','l10n_ve_rate'],

    # always loaded
    'data': [
        'views/res_partner.xml',
        "views/res_config_settings.xml"
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "binaural": True,
}
