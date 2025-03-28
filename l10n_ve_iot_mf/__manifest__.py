{
    "name": "Venezuela - IoT / Maquina Fiscal",
    
    "summary": "Implementación de DLLs de The Factory HKA (VE) y desarrollos PnP para Internet of Things (IoT) y compatibilidad con Odoo.",
    "description": """
        Implementación de DLLs de The Factory HKA (VE) y desarrollos PnP para Internet of Things (IoT) y
        compatibilidad con Odoo.
    """,
    "license": "LGPL-3",
    "category": "Accounting",
    "version": "17.0.0.0.5",
    "author": "binaural-dev",
    "website": "https://binauraldev.com",
    "depends": [
        "iot",
        "account",
        "web",
        "l10n_ve_invoice",
        "l10n_ve_tax_payer",
        "l10n_ve_stock_account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/iot_port.xml",
        "views/account_tax.xml",
        "views/account_move.xml",
        "views/iot_device.xml",
        "views/iot_box.xml",
        "views/account_journal.xml",
        "views/res_config_setting_views.xml",
        "views/account_move_views.xml",
        "wizards/accounting_reports_views.xml",
    ],
    "assets": {"web.assets_backend": ["l10n_ve_iot_mf/static/src/js/*.js"]},
    "installable": True,
    "application": False,
    "auto_install": False,
}
