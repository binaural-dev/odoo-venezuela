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
    "version": "17.0.1.0.0",
    "depends": ['stock'],
    "data": [
       'security/ir.model.access.csv',
        'security/security.xml',
        'views/brand_on_product.xml',
        'views/produc_brand_on_stock_move_line_inh.xml',
        'views/product_brand_on_product_variant.xml',
        'views/product_brand_on_stock_move_inh.xml',
        'views/product_brand_on_stock_quant_inh.xml',
        'views/product_brand_on_stock_warehouse.xml',
        'views/product_brand.xml',
        'views/product_template_brand.xml',
        'views/stock_picking_brand.xml',
    ],
    "application": True,
    "binaural":True,
}
