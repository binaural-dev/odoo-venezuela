{
    "name": "Cadipa Custom Ganaderia Website",
    "summary": "Modulo para Custom de Ganaderia en Sitio Web",
    "version": "17.0.1.0.0",
    "category": "Stock",
    "license": "LGPL-3",
    "author": "BinauralDev",
    'data': [
        # Security

        # Data
        "views/farming_template.xml",
    ],
    "depends": [
        "website",
        "binaural_farming_website",
    ],
    "assets": {
        "web.assets_frontend": [
        ]
    },
    'images': ['static/description/icon.png'],
    "installable": True,
    "application": True,
}