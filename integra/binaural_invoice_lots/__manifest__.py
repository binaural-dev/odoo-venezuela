{
    "name": "Binaural Facturacion Lotes",
    "summary": """
        Modulo destinado a Facturas en lote
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Stock",
    "version": "16.0.1.0.0",
    "depends": [
        "base",
        "stock",
        "product",
        "binaural_rate",
        "binaural_club_socios",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/product_template.xml",
        "views/res_config_settings.xml",
        "wizard/invoice_batch.xml",
    ],
    "binaural": True,
}
