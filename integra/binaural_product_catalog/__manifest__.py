{
    "name": "Binaural Catálogo de Productos",
    "summary": """
        Binaural Catálogo de Productos
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Stock/Inventory",
    "version": "16.0.1.0.7",
    "depends": ["stock", "sh_product_catalog_generator", "binaural_stock"],
    "data": [
        "views/product_template.xml",
        "views/product_product.xml",
        "views/res_config_settings.xml",
        "wizard/product_catalog_wizard_views.xml",
        "report/product_catalog_report_views.xml",
        "report/product_catalog_style_6_template.xml",
    ],
    "application": True,
    "binaural": True,
}
