{
    "name": "Venezuela - Base",
    "summary": """
        Módulo Base de la localización de Venezuela
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Technical",
    "version": "20.0.1.0.4",
    "depends": ["base", "web"],
    "auto_install": False,
    "data": [
        "views/res_config_settings_views.xml",
        "views/ir_module_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_base/static/src/core/debug/debug_menu_items.js",
        ],
    },
    "installable": True,
    "binaural_migrated": True,
}
