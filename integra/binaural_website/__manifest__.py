{
    "name": "Binaural Sitio Web",
    "summary": """
       Modulo para sitio web""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Website",
    "version": "17.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": ["binaural_location", "website_sale"],
    "data": [
        "data/ir_model_fields.xml",
        "views/profile_view.xml",
        "views/templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "binaural_website/static/src/js/website_sale_extend.js",
        ]
    },
    "application": True,
    "binaural": True,
}
