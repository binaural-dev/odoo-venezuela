{
    "name": "Binaural Inspeccion Fiscal Pos",
    "summary": """
        Módulo para permisos de inspeccion fiscal a Pos
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Technical",
    "version": "16.0.0.0.1",
    # any module necessary for this one to work correctly
    "depends": [
        "binaural_fiscal_inspector",
        "binaural_pos",
    ],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
    ],
    'auto_install': True,
    "binaural": True,
}
