{
    "name": "Binaural Inspeccion Fiscal Delivery",
    "summary": """
        Módulo para permisos de inspeccion fiscal a Delivery
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Technical",
    "version": "16.0.0.0.1",
    # any module necessary for this one to work correctly
    "depends": [
        "binaural_fiscal_inspector",
        "delivery",
    ],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
    ],
    'auto_install': True,
    "binaural": True,
}
