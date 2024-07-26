{
    "name": "Binaural Informes contables",
    "summary": """
        Módulo con modificaciones de los informes contables, adaptados a la normativa venezolana.
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "16.0.5.5.4",
    # any module necessary for this one to work correctly
    "depends": ["base", "account_reports", "binaural_accountant"],
    # always loaded
    "data": [
        "security/security.xml",
        "data/daily_ledger.xml",
        "data/result_statement.xml",
        "data/financial_situation_statement.xml",
        "data/account_report_actions.xml",
        "data/menuitems.xml",
        "views/account_report_views.xml",
    ],
    "binaural":True,
}
