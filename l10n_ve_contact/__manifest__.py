{
    "name": "Venezuela - Contacts",
    "summary": """
       Módulo para información de contactos de Venezuela""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Contacts/Contacts",
    "version": "16.0.1.0.7",
    # any module necessary for this one to work correctly
    "depends": ["base", "contacts", "l10n_ve_rate", "l10n_ve_location"],
    # always loaded
    "data": ["views/res_partner.xml", "views/res_config_settings.xml"],
    "images": ["static/description/icon.png"],
    "application": True,
}
