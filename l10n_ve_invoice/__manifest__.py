{
    "name": "Venezuela - Facturación",
    "summary": "Módulo de Facturación Venezuela",
    "description": """
Propósito
---------
Actualiza los tests del libro de compras internacional tras la
corrección del cálculo del alterno (moneda extranjera) en
l10n_ve_accountant/l10n_ve_tax. Ticket:
https://binaural.odoo.com/odoo/helpdesk.ticket/14463

Funcionalidades principales
---------------------------
* Sin cambios funcionales en el módulo. Se relaja la tolerancia de 3
  tests que comparaban `impuesto alterno == base alterna x tasa` con
  `places=2`: ahora que el impuesto se ancla al total real del asiento
  (y ya no se recalcula por separado desde la misma base), una base y un
  impuesto correctamente redondeados por separado pueden diferir del
  ideal matemático en unos centavos por orden de redondeo -- se usa
  `delta=1.0` para reflejar esa realidad en vez de exigir una igualdad
  que ya no aplica con el nuevo diseño unificado.

Cambios en UI / Modelos impactados
------------------------------------
* Solo se modifica un archivo de tests, ningún modelo ni vista.
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
