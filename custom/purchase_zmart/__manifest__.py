{
    "name": "Zmart Compras",
    "summary": """
       Modulo para compras personalizadas para smart""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Purchase/Purchase",
    "version": "16.0.0.9",
    "depends": [
        "binaural_purchase",
        "stock",
        "web",
    ],
    "data": [
        "security/ir.model.access.csv",
        'report/report_purchase.xml',
        "views/purchase_order.xml",
        "views/stock_picking.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "assets": {
        'web.assets_backend': [
            # 'purchase_zmart/static/**/*',
            'purchase_zmart/static/src/stock_forecasted/forecasted_details.xml',
            (
                "replace",
                "stock/static/src/stock_forecasted/stock_forecasted.js",
                "purchase_zmart/static/src/stock_forecasted/stock_forecasted.js",
            ),
        ],
    },
}
