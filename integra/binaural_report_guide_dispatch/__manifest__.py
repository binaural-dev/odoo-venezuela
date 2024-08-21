{
    "name": "Binaural Reporte de Guia de Despacho",
    "summary": """
       Modulo para crear reportes de guia de despacho sin sucursales""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "category": "IoT",
    "website": "https://binauraldev.com/",
    "version": "17.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": [
        "iot",
        "stock",
        "binaural_rate",
    ],
    # always loaded
    "data": [
        "data/dispatch_guide.xml",
        "views/stock_picking.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}