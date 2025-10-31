{
    "name": "Cadipa Reservas",
    "summary": "Modulo para personalizaciones de reservas de CADIPA",
    "version": "17.0.1.0.15",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Appointment",
    "depends": [
        "appointment_account_payment",
        "binaural_appointment",
        "web",
        "web_gantt",
        "calendar",
        "l10n_ve_rate",
    ],
    "data": [
        "views/res_config_settings.xml",
        "views/calendar_event_views.xml",
        "views/portal_my_memberships.xml",
    ],
    "images": [
        "static/description/icon.png"
    ],
    "application": True,
    "auto_install": True,
    "assets": {
        "web.assets_frontend": [
            "cadipa_appointment/static/src/js/guest_form.js",
        ],
    },
}
