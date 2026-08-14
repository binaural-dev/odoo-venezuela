{
    "name": "Venezuela - Auditoría - Base",
    "summary": """
        Base de auditoría de la localización de Venezuela.
        Provee el modelo extendido y monitoreo de requests salientes.
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Technical",
    "version": "19.0.0.0.0",
    "depends": [
        "auditlog",
        "l10n_ve_base",
    ],
    "data": [
        "views/auditlog_http_request_views.xml",
        "views/menu.xml",
        "views/res_config_settings.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": True
}
