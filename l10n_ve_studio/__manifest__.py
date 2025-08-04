{
    "name": "Venezuela - Studio",
    "summary": """
        Limitación de Odoo-Studio para la localización en Venezuela
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Base",
    "version": "18.0.0.0.1",
    # any module necessary for this one to work correctly
    "depends": ["l10n_ve_base"],
    "data": [],
    "images": ["static/description/icon.png"],
    "application": True,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
}
