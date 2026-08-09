{
    "name": "Venezuela - IGTF",
    "summary": "Módulo para campos del impuesto IGTF (Impuesto a las grandes transacciones financieras)",
    "description": """
Propósito
---------
Actualiza los tests de este módulo tras la corrección del cálculo del
alterno (moneda extranjera) en l10n_ve_accountant/l10n_ve_tax. Ticket:
https://binaural.odoo.com/odoo/helpdesk.ticket/14463

Funcionalidades principales
---------------------------
* Sin cambios funcionales en el módulo. Se eliminan las asignaciones a
  `foreign_rate` en el wizard de pago dentro de los tests: ese campo se
  volvió de solo lectura en un commit anterior de l10n_ve_accountant y su
  valor ya se calcula correctamente a partir de la moneda alterna y la
  fecha del pago.

Cambios en UI / Modelos impactados
------------------------------------
* Solo se modifican archivos de tests, ningún modelo ni vista.
""",
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "17.0.1.0.3",
        "depends": [
        "base",
        "l10n_ve_accountant",
        "l10n_ve_rate",
        "l10n_ve_tax",
        "l10n_ve_invoice",
        "l10n_ve_tax_payer",
    ],
       
    
    "data": [
        "views/account_journal.xml",
        "views/res_config_settings.xml",
        "report/invoice_free_form.xml",
        "wizard/account_payment_register.xml",
    ],
    "images": ["static/description/icon.png"],
    "assets": {
        "web.assets_backend": ["l10n_ve_igtf/static/src/components/**/*"],
    },
    "pre_init_hook": "pre_init_hook",
    "application": True,
}
