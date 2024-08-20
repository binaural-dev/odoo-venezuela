{
    "name": "Binaural Movil Sucursales",
    "summary": """
        Integración para app de vendedores con sucursales.
    """,
    "description": """
       Modulo para servir de integración con app de vendedores con sucursales. 
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "version": "16.0.1.0.3",
    "category": "Human Resources/Stock/Sales/Invoicing",
    "depends": [
        "binaural_mobile",
        "binaural_subsidiary"
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/analytic_account.xml"
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "binaural": True,
    "auto_install": True,
}
