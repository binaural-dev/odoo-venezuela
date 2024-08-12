{
    "name": "Binaural Ganaderia Website",
    "summary": "Modulo para información de Ganaderia en Sitio Web",
    "version": "17.0.1.0.0",
    "category": "Stock",
    "license": "LGPL-3",
    "author": "BinauralDev",
    'data': [
        # Security

        # Data

        # Views
        "views/farming_template.xml",
        "views/website_templates.xml",
        "views/snippets.xml",
    ],
    "depends": [
        "website",
        "binaural_farming",
    ],
    "assets": {
        "web.assets_frontend": [
            "binaural_farming_website/static/src/css/farming_template.css",
        ]
    },
    'images': ['static/description/icon.png'],
    "installable": True,
    "application": True,
}