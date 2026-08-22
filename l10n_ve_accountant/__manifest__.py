{
    "name": "Venezuela - Contabilidad",
    "summary": "Módulo de Contabilidad Venezuela",
    "description": """
Propósito
---------
Módulo base de contabilidad de la localización venezolana: numeración
correlativa de comprobantes, unidad tributaria, cálculo y seguimiento del
monto equivalente en moneda alterna (extranjera) a lo largo de todo el
ciclo contable (facturas, pagos, extractos bancarios, conciliaciones), y
los reportes/asistentes contables propios de Venezuela.

Funcionalidades principales
---------------------------
* Numeración de comprobantes única por contacto/diario/estado, y gestión
  de la Unidad Tributaria (``tax.unit``).
* Cálculo de la moneda alterna en cada punto del ciclo contable: precio
  unitario y subtotal de línea, impuestos, términos de pago, extractos
  bancarios y conciliaciones -- siempre anclado al total real del
  documento/asiento para que coincida con lo que ve el usuario en el
  wizard de pago.
* Distribución del "real portion" (ajuste de redondeo entre la moneda de
  la compañía y la de terceros) sin afectar nunca las líneas de impuesto.
* Alerta de límite de crédito del cliente al confirmar una factura de
  venta, y bloqueo de edición de tasas de cambio salvo para el grupo
  autorizado.
* Wizard de registro de pagos con tasa alterna, reportes de detalle de
  factura y de pagos, y asistente de alerta al publicar un asiento.

Cambios en UI / Modelos impactados
------------------------------------
* Modifica ``account.move``, ``account.move.line``, ``account.payment``,
  ``account.bank.statement.line``, ``account.payment.term``,
  ``res.currency``, ``res.partner`` y ``res.company``; agrega el modelo
  ``tax.unit``.
* Vistas de factura, apunte contable, pago, contacto, moneda, ajustes de
  configuración y el wizard de registro de pagos; reportes de detalle de
  factura y de pagos.
""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Localizations/Account Chart",
    "version": "17.0.0.0.62",
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
