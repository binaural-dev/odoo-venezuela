{
    "name": "Venezuela - Base",
    "summary": """
        Módulo Base de la localización de Venezuela
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Technical",
    "version": "18.0.0.0.0",
    "depends": ["base", "web"],
    "auto_install": False,
    "data": ["security/ir.model.access.csv", "views/res_config_settings_views.xml"],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_base/static/src/core/debug/debug_menu_items.js",
        ],
    },
}
