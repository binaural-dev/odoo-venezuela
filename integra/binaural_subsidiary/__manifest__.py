{
    "name": "Binaural Sucursales",
    "summary": """
        Integración de Sucursales en Contabilidad A..
    """,
    "description": """
       Modulo para servir de integración de sucursales. 
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "version": "0.2",
    "category": "Accountant",
    "depends": [
        "binaural_accountant",
        # "binaural_sale",
        # "binaural_invoice",
        "binaural_rate",
    ],
    "data": [
        # "security/ir.model.access.csv",
        # "data/ir_rule.xml",
        # "data/res_groups.xml",
        "views/res_config_settings.xml",
        "views/account_move.xml",
        "views/sale_order_views.xml"
    ],
    "assets": {
        "web.assets_frontend": [
            # "binaural_mobile/static/src/js/portal_budget.js",
        ]
    },
    "images": ["static/description/icon.png"],
    "application": True,
}