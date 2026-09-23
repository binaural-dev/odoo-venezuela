{
    "name": "Venezuela - Máquina Fiscal (Base Web Serial)",
    "summary": "Driver base Web Serial API para impresoras fiscales The Factory HKA (TFHKA).",
    "license": "LGPL-3",
    "category": "Accounting",
    "version": "17.0.1.0.0",
    "author": "Binaural",
    "website": "https://binauraldev.com",
    "depends": ["web"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_mf_base/static/src/core/*.js",
            "l10n_ve_mf_base/static/src/drivers/*.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
