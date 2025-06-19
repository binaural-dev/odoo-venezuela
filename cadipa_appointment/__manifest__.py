{
    "name": "Cadipa Reservas",
    "summary": """
       Modulo para personalizaciones de reservas de CADIPA """,
    "version": "17.0.1.0.0",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Appointment",
    # any module necessary for this one to work correctly
    "depends": [
        "web",
        "web_gantt",
        "calendar",
        "binaural_appointment",
        "l10n_ve_rate"
    ],
    # always loaded
    "data": [
        "views/res_config_settings.xml",
        "views/calendar_event_views.xml",
    ],
    "images": [
        "static/description/icon.png"
    ],
    "application": True,
    "auto_install": True,
}
