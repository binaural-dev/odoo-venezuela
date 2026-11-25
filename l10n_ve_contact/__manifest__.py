{
    "name": "Venezuela - Contactos",
    "summary": """
       Módulo para información de contactos de Venezuela
    """,
    "license": "LGPL-3",
    "description": """
       Módulo para información de contactos de Venezuela
    """,
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Contacts/Contacts",
    "version": "19.0.1.8.2",
    "depends": ["base", "contacts", "account", "l10n_ve_rate", "l10n_ve_location"],
    "data": [
        "security/res_groups.xml",
        "security/ir.model.access.csv",
        "views/res_partner.xml",
        "views/res_config_settings.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_contact/static/src/fields/**/*",
        ],
        # The PoS opens the contact form of the backend in a dialog
        # (point_of_sale.res_partner_action_edit_pos), so the CI/RIF widget
        # must be in its bundle too; without it the field falls back to the
        # plain char field and takes letters again. Declaring it does nothing
        # while point_of_sale is not installed.
        "point_of_sale._assets_pos": [
            "l10n_ve_contact/static/src/fields/**/*",
        ],
        "web.assets_unit_tests": [
            "l10n_ve_contact/static/tests/unit/**/*",
        ],
    },
    "images": ["static/description/icon.png"],
    "application": True,
}
