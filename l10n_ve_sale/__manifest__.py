{
    "name": "Venezuela - Sales",
    "summary": """
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Sales/Sales",
    "version": "16.0.1.1.4",
    # any module necessary for this one to work correctly
    "depends": [
        "base",
        "l10n_ve_tax",
        "sale_management",
        "l10n_ve_rate",
        "l10n_ve_contact",
        "l10n_ve_invoice",
        "l10n_ve_filter_partner",
    ],
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
}
