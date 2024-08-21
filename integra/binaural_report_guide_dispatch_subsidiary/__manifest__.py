{
    "name": "Binaural Reporte de Guia de Despacho de las sucursales",
    "summary": """
       Modulo para crear reportes de guia de despacho con las sucursales""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "category": "IoT",
    "website": "https://binauraldev.com/",
    "version": "17.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": [
        "binaural_report_guide_dispatch",
        "binaural_subsidiary",
    ],
    # always loaded
    "data": [
        "data/dispatch_guide.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}
