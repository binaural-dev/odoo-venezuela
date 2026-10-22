{
    "name": "Venezuela - Guía de Despacho / Flota",
    "summary": "Llena los datos de transporte de la guía de despacho desde Flota",
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://www.binauraldev.com",
    "category": "Inventory/Inventory",
    "version": "19.0.1.0.2",
    "depends": [
        "l10n_ve_stock_account",
        "fleet",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/fleet_vehicle_views.xml",
        "views/res_partner_views.xml",
        "views/stock_picking_views.xml",
    ],
    "images": ["static/description/icon.png"],
    "auto_install": True,
    "application": False,
}
