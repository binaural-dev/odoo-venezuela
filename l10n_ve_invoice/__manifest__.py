{
    "name": "Binaural Facturación",
    "summary": """
       Modulo para contabilidad Venezolana """,
    "version": "16.0.3.2.9",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Localizations/Account Chart",
    # any module necessary for this one to work correctly
    "depends": [
        "l10n_ve_accountant",
        "l10n_ve_contact",
        "l10n_ve_tax",
        "od_journal_sequence",
        "l10n_ve_filter_partner",
    ],
    # always loaded
    "data": [
        "security/binaural_invoice_groups.xml",
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "data/account_data.xml",
        "data/invoice_free_form_paperformat.xml",
        "data/invoice_sale_note_paperformat.xml",
        "report/report_invoice_free_form.xml",
        "report/report_invoice_sale_note.xml",
        "report/report_invoice.xml",
        "views/account_move.xml",
        "views/account_journal_views.xml",
        "views/res_config_settings.xml",
        "views/menu.xml",
        "wizard/accounting_reports_views.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "binaural": True,
}
