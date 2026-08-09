{
    "name": "Venezuela - Contabilidad",
    "summary": "Módulo de Contabilidad Venezuela",
    "description": """
Propósito
---------
Corrige el cálculo del alterno (moneda extranjera) en facturas y pagos:
el total mostrado al usuario en el wizard de pago no coincidía con el que
mostraba la cuenta por cobrar/pagar de la factura, por unos centavos de
diferencia. Ticket: https://binaural.odoo.com/odoo/helpdesk.ticket/14463

Funcionalidades principales
---------------------------
* El impuesto alterno de cada línea de la factura se ancla al total del
  documento (`amount_total x tasa`) en vez de recalcularse por producto,
  garantizando que la cuenta por cobrar/pagar coincida con el wizard de
  pago sin importar cuántas líneas o tasas de impuesto tenga el documento.
* Reparto determinístico de centavos de redondeo entre líneas de impuesto
  mediante el método del "mayor residuo" (largest remainder), en O(n) para
  evitar cuelgues cuando el monto a repartir es grande.
* Corrección de precisión del precio unitario alterno (`foreign_price`),
  que antes se truncaba a 2 decimales aunque la precisión configurada
  ("Foreign Product Price") fuera mayor.
* Ajuste del "real portion" (redondeo entre moneda base y de terceros) para
  que la diferencia siempre la absorba una línea de producto, nunca una de
  impuesto.
* El monto alterno mostrado como "conciliado" en un pago parcial ahora usa
  la tasa del lado que no es la factura (pago o extracto), no la tasa
  histórica de la factura.

Cambios en UI / Modelos impactados
------------------------------------
* Modifica ``account.move`` (nuevos métodos ``_apportion_largest_remainder``,
  ``_compute_foreign_tax_balance``, ``_distribute_foreign_pt_residual``,
  ``_distribute_invoice_real_portion``) y ``account.move.line``
  (``foreign_price``, ``_prepare_reconciliation_single_partial``).
* Se elimina la herencia de ``bank_rec_widget`` (dejó de usarse).
""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Localizations/Account Chart",
    "version": "17.0.0.0.60",
    "depends": [
        "base",
        "web",
        "account",
        "account_reports",
        "l10n_ve_tax",
        "l10n_ve_contact",
        "l10n_ve_rate",
        "account_debit_note"
    ],
    "data": [
        "security/res_groups.xml",
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "data/account_data.xml",
        "data/ir_actions_server.xml",
        "data/paperformats.xml",
        "data/tax_unit_data.xml",
        "views/account_invoice_report.xml",
        "views/account_move.xml",
        "views/account_move_line.xml",
        "views/account_payment.xml",
        "views/res_partner.xml",
        "views/res_currency_views.xml",
        "views/ir_property.xml",
        "views/res_company_views.xml",
        "views/tax_unit.xml",
        "views/res_config_settings_views.xml",
        "views/menuitem_views.xml",
        "report/account_invoice_details.xml",
        "report/all_payment_report.xml",
        "report/account_report_templates.xml",
        "report/account_report_document.xml",
        "report/account_template_report_views.xml",
        "report/report_invoice.xml",
        "wizard/account_payment_register.xml",
        "wizard/invoices_details.xml",
        "wizard/payment_report.xml",
        "wizard/move_action_post_alert_views.xml",
    ],
     "assets": {
        "web.assets_backend": ["l10n_ve_accountant/static/src/js/*"],
    },
    "images": ["static/description/icon.png"],
    "application": True,
    "pre_init_hook": "pre_init_hook",
}
