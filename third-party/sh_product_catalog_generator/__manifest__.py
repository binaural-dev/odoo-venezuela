# Part of Softhealer Technologies.
{
    "name": "Product Catalog Generator",

    "author": "Softhealer Technologies",

    "support": "support@softhealer.com",

    "website": "https://www.softhealer.com",

    "category": "Extra Tools",

    "license": "OPL-1",

    "summary": "Create Product Catalogue, Custom Product Catalog App, Make Own Product Catalog, Product Catalogue Module, Customize Product Catalogue, Product Catalog Template, Design Product Catalog, Product Catalog Management, Product Catalogue Builder Odoo",

    "description": """Do you want to represent products in multiple catalogs? Do you want different catalog styles? so you are at the right place. This module helps you to customize the product catalog with the custom style. Here you can design your catalog with catalog type, catalog styles, image option with sizes, box per row, page break, show/hide price, show/hide description, show/hide product link, show/hide internal reference. You can develop your own catalog using this different customization. You can send the product catalog by email. We provide security groups for the product catalog. Generate Product Catalog Odoo, Create Custom Product Catalog, Make Own Product Catalog, Product Catalogue Module, Customize Product Catalogue, Product Catalog Template, Design Product Catalog, Develop Product Catalogue, Product Catalog Management, Product Catalogue Builder Odoo, Create Product Catalogue, Custom Product Catalog App, Make Own Product Catalog, Product Catalogue Module, Customize Product Catalogue, Product Catalog Template, Design Product Catalog, Develop Product Catalogue, Product Catalog Management, Product Catalogue Builder Odoo""",

    "version": "17.0.1.0.0",

    "depends": [
        'sale_management',
        'product',
        'website_sale',
        'utm'
    ],

    "data": [
        'security/product_catalog_groups.xml',
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
        'views/main_menus.xml',
        'views/product_catalog_views.xml',
        'views/default_after_pages_views.xml',
        'views/default_before_pages_views.xml',
        'wizard/product_catalog_wizard_views.xml',
        'report/product_catalog_report_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sh_product_catalog_generator/static/src/scss/style.scss',
        ],

    },

    "images": ['static/description/background.png', ],
    "live_test_url": "https://youtu.be/p-ZjK6qRWB8",
    "auto_install": False,
    "application": True,
    "installable": True,
    "price": "60",
    "currency": "EUR"
}
