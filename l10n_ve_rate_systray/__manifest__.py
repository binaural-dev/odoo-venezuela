{
    "name": "Venezuela - Tasa del día en la barra superior",
    "summary": """
        Muestra la tasa de la moneda foránea en la barra superior del backend
    """,
    "description": """
        Agrega a la barra superior del backend la última tasa registrada de la
        moneda foránea de la compañía (p. ej. Bs por USD). Se pinta con fondo
        verde si es la tasa de hoy y con fondo rojo si es de una fecha anterior
        o no hay tasa. Se activa por compañía desde Ajustes generales, donde
        también se elige qué moneda mostrar. Solo depende de módulos nativos.
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Technical",
    "version": "17.0.1.0.1",
    "depends": ["web", "base_setup"],
    "images": ["static/description/icon.png"],
    "data": [
        "views/res_config_settings.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_rate_systray/static/src/currency_rate_badge/*",
            "l10n_ve_rate_systray/static/src/systray/*",
        ],
    },
}
