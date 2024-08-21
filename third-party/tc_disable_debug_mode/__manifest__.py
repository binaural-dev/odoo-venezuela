{
    "name": "Disable Developer Mode",
    "summary": """Allow to Disable Developer Mode or Disable Debug Mode For Users.""",
    "category": "Tools",
    "version": "17.0.1.0.0",
    "sequence": 7,
    "website": "https://www.titanscodetech.com",
    "author": "Titans Code Tech",
    "license": "OPL-1",
    "description": """
        Allow to Disable Debug Mode or Disable Developer Mode For Users.""",
    "depends": [
        "base",
    ],
    "data": [
        "security/security.xml",
    ],
    "images": ["static/description/Banner.gif"],
    "application": True,
    "installable": True,
    "auto_install": False,
    "price": 10,
    "currency": "USD",
    "pre_init_hook": "pre_init_check",
}
