{
    "name": "Binaural Ventas",
    "summary": """
       Modulo para ventas """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Sales/Sales",
    "version": "17.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": [
        "base",
        "binaural_tax",
        "sale_management",
        "binaural_rate",
        "binaural_contact",
        "binaural_invoice",
        "binaural_filter_partner",
    ],
    # always loaded
    "data": [
        "security/res_groups.xml",
        "data/ir_cron.xml",
        "views/res_config_settings.xml",
        "views/sale_order.xml",
        "views/product_pricelist_item_views.xml",
        "views/menuitems.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "binaural": True,
}
