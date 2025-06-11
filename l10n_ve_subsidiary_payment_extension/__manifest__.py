{
    "name": "Venezuela - Retenciones/Sucursales",
    "summary": """
        Modulo para agregar sucursales (cuentas analiticas) a los pagos de retenciones.
    """,
    "author": "binaural-dev",
    "website": "https://www.binauraldev.com",
    "category": "Uncategorized",
    "version": "17.0.1.0.0",
    "depends": ["l10n_ve_payment_extension", "l10n_ve_subsidiary"],
    "data": [
        "security/ir_rule.xml",
        "report/retention_line_report_views.xml",
        "views/account_retention_iva.xml",
        "views/analytic_account.xml",
        "views/res_config_settings.xml",
        "wizard/municipal_retention_patent_report.xml",
        "wizard/municipal_retention_xlsx_report.xml",
    ],
    "auto_install": True,
    "license": "LGPL-3",
}
