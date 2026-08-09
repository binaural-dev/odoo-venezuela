{
    "name": "Venezuela - Facturación",
    "summary": "Módulo de Facturación Venezuela",
    "description": """
Propósito
---------
Provee la facturación electrónica de la localización venezolana: el
libro de compras y ventas exigido por el SENIAT, la numeración
correlativa por diario, el formato de factura libre y la integración
con notas de débito.

Funcionalidades principales
---------------------------
* Wizard de reportes contables para generar el libro de compras y el
  libro de ventas (nacional e internacional), con el desglose de bases
  imponibles por alícuota y el monto equivalente en moneda alterna.
* Numeración de secuencias única por diario (``ir.sequence``).
* Reporte e impresión de factura en formato libre.
* Integración con notas de débito (``account.debit.note``) propia de la
  localización.
* Grupos de seguridad y reglas de acceso específicas del módulo.

Cambios en UI / Modelos impactados
------------------------------------
* Modifica ``account.move``, ``account.journal``, ``account.move.line``,
  ``account.payment``, ``ir.sequence`` y ``account.debit.note``.
* Vistas de factura, diario, notas de débito, menú y ajustes de
  configuración; wizard y reportes de libro de compras/ventas y de
  factura de forma libre.
""",
    "version": "17.0.1.0.5",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Localizations/Account Chart",
    "depends": [
        "l10n_ve_rate",
        "l10n_ve_base",
        "l10n_ve_accountant",
        "l10n_ve_contact",
        "l10n_ve_tax",
        "l10n_ve_filter_partner",
        "od_journal_sequence",
        "account_debit_note",
    ],
    "data": [
        "security/l10n_ve_invoice_groups.xml",
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "data/account_data.xml",
        "data/invoice_free_form_paperformat.xml",
        "report/report_ir_actions_report.xml",
        "report/report_invoice_free_form.xml",
        "views/account_move.xml",
        "views/account_journal_views.xml",
        "views/res_config_settings.xml",
        "views/menu.xml",
        "wizard/accounting_reports_views.xml",
        "views/account_debit_note_view.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "pre_init_hook": "pre_init_hook",
}
