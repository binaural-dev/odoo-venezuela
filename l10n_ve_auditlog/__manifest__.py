{
    "name": "Venezuela - Auditoría",
    "summary": """
        Módulo de Auditoría de la localización de Venezuela
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Technical",
    "version": "1.2",
    "data": [
        "security/res_groups.xml",
        "security/ir.model.access.csv",
        "views/auditlog_lines_views.xml",
        "views/auditlogs_views.xml",
    ],
    "depends": [
        "auditlog",
        "l10n_ve_accountant",
        "l10n_ve_payment_extension",
    ],
}
