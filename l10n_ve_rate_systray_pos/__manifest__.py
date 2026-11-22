{
    "name": "Venezuela - Tasa del día en la barra del POS",
    "summary": """
        Muestra la tasa de la moneda configurada en la barra superior del POS
    """,
    "description": """
        Lleva al Punto de Venta el mismo recuadro de tasa del backend
        (l10n_ve_rate_systray): fondo verde si es la tasa de hoy, rojo si es de
        una fecha anterior o no hay tasa. Usa el check y la moneda configurados
        por compañía. Se instala solo cuando están el POS y l10n_ve_rate_systray.
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Sales/Point of Sale",
    "version": "19.0.1.0.0",
    "depends": ["point_of_sale", "l10n_ve_rate_systray"],
    "images": ["static/description/icon.png"],
    "data": [],
    "assets": {
        "point_of_sale._assets_pos": [
            "l10n_ve_rate_systray/static/src/currency_rate_badge/*",
            "l10n_ve_rate_systray_pos/static/src/navbar/*",
        ],
    },
    "auto_install": True,
}
