{
    "name": "Binaural Nomina Y Retenciones",
    "summary": """
       Modulo de extensiones de pago y nomin """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accountant/Accountant",
    "version": "17.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": [
        "binaural_payment_extension",
        "binaural_hr_payroll"
    ],
    # always loaded
    "data": [],
    "images": ["static/description/icon.png"],
    "application": True,
    "binaural": True,
    "auto_install": True,
}
