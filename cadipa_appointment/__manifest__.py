{
    "name": "Cadipa Reservas",
    "summary": "Modulo para personalizaciones de reservas de CADIPA",
    "version": "17.0.1.0.4",
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
        "views/appointment_templates_appointments.xml",
        "views/appointment_form_hidden_fields.xml",
        "views/appointment_templates_validation.xml",
        "views/portal_invoice_seller.xml",
        "views/portal_my_memberships.xml",

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
}
