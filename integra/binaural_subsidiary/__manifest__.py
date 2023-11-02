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
    "version": "0.1",
    "category": "Human Resources/Stock/Sales/Invoicing",
    "depends": [
        "binaural_sale",
        "binaural_invoice",
        "binaural_rate",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_rule.xml",
        "data/res_groups.xml",
        "views/res_config_settings.xml"
    ],
    "assets": {
        "web.assets_frontend": [
            "binaural_mobile/static/src/js/portal_budget.js",
        ]
    },
    "images": ["static/description/icon.png"],
    "application": True,
}