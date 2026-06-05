{
    "name": "Cadipa Reservas",
    "summary": "Modulo para personalizaciones de reservas de CADIPA",
    "version": "17.0.1.0.28",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Appointment",
    "depends": [
        "appointment_account_payment",
        "binaural_appointment",
        "binaural_memberships",
        "web",
        "web_gantt",
        "calendar",
        "l10n_ve_rate",
        "binaural_memberships",
    ],
    "data": [
        "data/cron.xml",
        "views/res_config_settings.xml",
        "views/calendar_event_views.xml",
        "views/portal_my_memberships.xml",
        "views/appointment_template_registration.xml",
        "views/secuence_menuitem.xml"
    ],
    "images": [
        "static/description/icon.png"
    ],
    "assets": {
        "web.assets_frontend": [
            "cadipa_appointment/static/src/xml/appointment_slots.xml",
            "cadipa_appointment/static/src/js/appointment_slot.js",
        ],
    },
    "application": True,
    "auto_install": True,
    "assets": {
        "web.assets_frontend": [
            "cadipa_appointment/static/src/js/guest_form.js",
        ],
    },
}
