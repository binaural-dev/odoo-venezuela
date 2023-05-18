# -*- coding: utf-8 -*-
{
    "name": "Binaural Inventario",
    "summary": """
        Modulo de localización relacionado
        al inventario.
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Stock",
    "version": "16.0.0.0.1",
    "depends": ["stock", "binaural_rate"],
    "data": [
        # 'security/ir.model.access.csv',
        "security/security_binaural_stock.xml",
        "views/product_category_views.xml",
        "views/res_config.xml",
    ],
}
