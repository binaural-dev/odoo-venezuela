{
    "name": "Binaural Sincronización de Tasa",
    "summary": """
        Módulo para establecer la tasa oficial de venecuela "tasa BCV" de manera automatica
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Technical",
    "version": "16.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": ["binaural_rate", "currency_rate_live"],
    # always loaded
    "data": [
        "views/res_config_settings.xml",
    ],
}
