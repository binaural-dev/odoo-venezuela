{
    "name": "Binaural IoT - Máquina Fiscal",
    "version": "17.0.1.0.1",
    "category": "Accounting",
    "summary": "The Factory HKA (SDK) y Pnp Desarrollos en IoT",
    "license": "LGPL-3",
    "description": """
    Implementacion de SDK de The Factory HKA (VE) y PnP desarrollos a Internet of Things (IoT) y
    compatibilidad con Odoo.
    """,
    "sequence": "1",
    "author": "Binaural C.A - Odoo Gold Partner",
    "support": "contacto@binaural.dev",
    "website": "https://binauraldev.com",
    "depends": ["iot", "account", "web", "l10n_ve_invoice", "l10n_ve_tax_payer"],
    "data": [
        "data/iot_port.xml",
        "views/account_tax.xml",
        "views/account_move.xml",
        "views/iot_device.xml",
        "views/iot_box.xml",
        "views/account_journal.xml",
        "wizards/accounting_reports_views.xml",
        "security/ir.model.access.csv",
    ],
    "assets": {
        "web.assets_backend": [
            "binaural_iot_mf/static/src/js/*.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
    "binaural": True,
}
