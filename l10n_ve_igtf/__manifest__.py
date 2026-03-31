{
     "name": "Venezuela - Anticipos e IGTF",
    "summary": "Gestión de pagos anticipados y aplicación del impuesto IGTF en facturación y pagos.",
    "license": "LGPL-3",
    "description": """
    Localización Venezolana: Anticipos e IGTF
    =========================================
    Este módulo unifica la gestión de anticipos contables con el Impuesto a las Grandes Transacciones Financieras (IGTF).

    Características principales:
    ---------------------------
    * Registro y control de anticipos de clientes y proveedores.
    * Configuración de cuentas puente de anticipos por compañía.
    * Aplicación automática y manual del IGTF (3%) en pagos y facturas.
    * Widget de conciliación de anticipos en facturas.
    * Soporte para pagos multimoneda y validación de diarios de efectivo/banco.
    * Integración de flujos de cancelación de anticipos mediante asistente.
    """,
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "19.0.2.0.0",

    "depends": [
        "base",
        "l10n_ve_accountant",
        "l10n_ve_invoice",
        "l10n_ve_tax_payer",
        "l10n_ve_base",
    ],
    "data": [
        "security/res_groups.xml",
        "security/ir.model.access.csv",
        "views/account_journal.xml",
        "views/account_account.xml",
        "views/account_move.xml",
        "views/account_payment.xml",
        "wizard/account_payment_register.xml",
        "views/res_config_settings.xml",
        "views/res_partner.xml",
        "wizard/move_action_cancel_advance_payment.xml",
        
    ],
    "images": ["static/description/icon.png"],
    "assets": {
        "web.assets_backend": ["l10n_ve_igtf/static/src/components/**"],
    },
    "application": True,
}
