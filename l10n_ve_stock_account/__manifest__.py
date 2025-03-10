{
    "name": "Venezuela - Stock Account",
    "summary": """
        Stock Accoun for Venezuela Localization
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://www.binauraldev.com",
    "category": "Stock Account",
    "version": "16.0.1.0.9",
    "depends": [
        "l10n_ve_stock",
        "l10n_ve_accountant",
        "stock_move_invoice",
        "l10n_ve_sale",
        "stock_move_invoice"
    ],
    "data": [

        "security/ir.model.access.csv",

        "data/ir_sequence.xml",
        "data/dispatch_guide_paperformat.xml",
        'data/transfer_reason.xml',

        "views/account_move_views.xml",
        "views/stock_picking_guide_dispatch_views.xml",
        "views/stock_picking_views.xml",
        "views/sale_order_views.xml",
        "views/res_partner_view.xml",
        "views/menuitem_views.xml",

        "report/dispatch_guide.xml",
        "report/dispatch_guide_template.xml",
        
    ],
    "application": True,
    'auto_install': True,
}
