{
    "name": "Binaural Informes contables",
    "summary": """
        Módulo con modificaciones de los informes contables, adaptados a la normativa venezolana.
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "16.0.0.0.1",
    # any module necessary for this one to work correctly
    "depends": ["base", "account_reports", "binaural_accountant"],
    # always loaded
    "data": [
        "data/account_report_actions.xml",
        "views/menuitems.xml",
    ],
}
