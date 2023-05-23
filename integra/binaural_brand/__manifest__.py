{
    "name": "Binaural Marca",
    "summary": """
        Maestro de marca en productos
parroquias. 
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Stock/Inventory",
    "version": "16.0.0.1",
    "depends": ['stock', 'sale', 'purchase','account'],
    "data": [
       'security/ir.model.access.csv',
        'views/account_move_form_inh_brand.xml',
        'views/brand_on_product.xml',
        'views/produc_brand_on_stock_move_line_inh.xml',
        'views/product_brand_on_product_variant.xml',
        'views/product_brand_on_stock_move_inh.xml',
        'views/product_brand_on_stock_quant_inh.xml',
        'views/product_brand_on_stock_warehouse.xml',
        'views/product_brand_stock_valuation_inh.xml',
        'views/product_brand.xml',
        'views/product_template_brand.xml',
        'views/purchase_form_inh_brand.xml',
        'views/sale_form_inh_brand.xml',
        'views/stock_picking_brand.xml',
        'reports/report_purchase.xml',
        'reports/report_purchase_order.xml',
        'reports/report_sale.xml',
    ],
    "application": True,
}
