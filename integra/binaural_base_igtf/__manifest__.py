{
    "name": "Binaural Technical IGTF",
    "summary": "Modulo para campos del impuesto IGTF (Impuesto a las grandes transacciones financieras)",
    "license": "AGPL-3",
    "description": "Modulo para campos del impuesto IGTF (Impuesto a las grandes transacciones financieras)",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "1.0",
    "depends": ["base","binaural_rate", "binaural_tax"],
    "data": ["views/res_config_settings.xml"],
    "images": ["static/description/icon.png"],
    "assets": {
        "web.assets_backend": ["binaural_igtf/static/src/components/**/*"],
    },
    "application": True,
}
