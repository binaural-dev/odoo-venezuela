{
    "name": "Binaural Website POS Sale",
    "summary": """
       Modulo para Localizacion Venezolana en POS y Ventas""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "category": "Point of Sale",
    "website": "https://binauraldev.com/",
    "version": "16.0.0.0.0",
    # any module necessary for this one to work correctly
    "depends": ["base", "point_of_sale", "pos_sale", "website", "sales_team"],
    # always loaded
    "data": ["views/res_config_settings.xml"],
    "images": ["static/description/icon.png"],
    "application": True,
    "assets": {
        "point_of_sale.assets": [
            (
                "replace",
                "pos_sale/static/src/js/OrderManagementScreen/SaleOrderFetcher.js",
                "binaural_pos_website/static/src/js/SaleOrderFetcher.js",
            ),
        ],
    },
}
