{
    "name": "Venezuela - Base",
    "summary": """
        Módulo Base de la localización de Venezuela
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Technical",
    "version": "17.0.0.0.0",
    "depends": ["base", "web"],
    "auto_install": True,
    "data": ["security/ir.model.access.csv", "data/ir_config_parameter.xml"],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_base/static/src/core/debug/debug_menu_items.js",
        ],
    },
}

