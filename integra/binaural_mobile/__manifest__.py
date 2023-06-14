{
    "name": "Binaural Movil",
    "summary": """
        Integración para app de vendedores..
    """,
    "description": """
       Modulo para servir de integración con app de vendedores. 
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "version": "16.2",
    "category": "Human Resources/Stock/Sales/Invoicing",
    "depends": [
        "web",
        "website",
        "portal",
        "website_sale",
        "binaural_brand",
        "binaural_seller",
        "binaural_sale",
        "binaural_stock",
    ],
    "data": [
        # "security/ir.model.access.csv",
        "data/ir_rule.xml",
        "views/hr_employee.xml",
        "views/portal_budget.xml",
        "views/website_templates.xml",
        "views/portal_templates.xml",
        "views/portal_invoice_seller.xml",
        "views/res_config_settings.xml",
        "views/sale_order_views.xml",
        "views/templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "binaural_mobile/static/src/js/portal_budget.js",
            "binaural_mobile/static/src/js/portal_invoice.js",
        ]
    },
    "images": ["static/description/icon.png"],
    "application": True,

}