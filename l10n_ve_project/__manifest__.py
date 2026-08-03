{
    "name": "Venezuela - Proyectos",
    "summary": """
        Módulo de Proyectos Venezuela
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Project",
    "version": "19.0.1.0.0",
    "depends": [
        "sale_project",
        "project_purchase",
        "l10n_ve_sale",
        "l10n_ve_rate",
        "l10n_ve_accountant",
    ],
    "data": [],
    "demo": [],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_project/static/src/components/**/*",
        ],
    },
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": False,
    "auto_install": False,
}
