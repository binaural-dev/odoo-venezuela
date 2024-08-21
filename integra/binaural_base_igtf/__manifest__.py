{
    "name": "Binaural Technical IGTF",
    "summary": "Modulo para campos del impuesto IGTF (Impuesto a las grandes transacciones financieras)",
    "license": "AGPL-3",
    "description": "Modulo para campos del impuesto IGTF (Impuesto a las grandes transacciones financieras)",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "17.0.1.0.0",
    "depends": [
        "base",
        "binaural_rate",
        "binaural_tax",
        "binaural_invoice",
        "binaural_tax_payer",
        "binaural_base",
    ],
    "data": [
        "views/res_config_settings.xml",
        "views/res_company.xml",
        "report/invoice_free_form.xml",
    ],
    "images": ["static/description/icon.png"],
    "assets": {
        "web.assets_backend": ["binaural_base_igtf/static/src/components/**/*"],
    },
    "application": True,
    "binaural": True,
}
