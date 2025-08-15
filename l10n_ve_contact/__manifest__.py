{
    "name": "Venezuela - Contactos",
    "summary": """
       Módulo para información de contactos de Venezuela
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Contacts/Contacts",
    "version": "18.0.0.0.3",
    "depends": ["base", "contacts", "account", "l10n_ve_rate", "l10n_ve_location"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner.xml",
        "views/res_config_settings.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}
