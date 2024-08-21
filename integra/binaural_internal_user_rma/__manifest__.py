{
    "name": "Binaural usuario interno para RMA",
    "summary": """
            Modulo para crear regla de acceso que permite  a un usuario interno 
            sin ningun otro permiso a crear notas RMA
            """,
    "version": "17.0.1.0.0",
    "development_status": "Production/Stable",
    "category": "RMA",
    "website": "https://binauraldev.com/",
    "author": "Binauraldev",
    "license": "AGPL-3",
    "depends": ["rma", "product"],
    "data": [
        "security/ir.model.access.csv",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "binaural": True,
}
