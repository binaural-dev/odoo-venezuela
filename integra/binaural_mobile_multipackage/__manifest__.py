{
    "name": "Binaural Móvil Multi-Empaquetados",
    "summary": "Implementacion de Binaural Móvil",
    "version": "16.0.0.0.7",
    "category": "Accounting",
    "license": "LGPL-3",
    "author": "BinauralDev",
    "depends": [
        "binaural_mobile"
    ],
    "data": [
        "views/res_config_settings.xml",
        "views/mobile_modal_multiple_packaging.xml",
        "views/portal_budget.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "binaural_mobile_multipackage/static/src/js/*js",
        ]
    },
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": True,
}
