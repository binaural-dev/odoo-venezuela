{
    "name": "Binaural Reservas",
    "summary": """
       Modulo para reservaciones""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Appointment",
    "version": "16.0.1.1.1",
    # any module necessary for this one to work correctly
    "depends": [
        "base",
        "web",
        "portal",
        "stock",
        "appointment",
        "website_appointment",
        "appointment_hr",
        "appointment_crm",
        "appointment_sms",
        "website_appointment_crm",
        "stock",
        "product",
        "binaural_contact",
        "crm",
        "event_crm",
        "sale_crm",

    ],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "views/product_template.xml",
        "views/appointment_templates_registration.xml",
        "views/appointment_type_views.xml",
        "views/crm_lead.xml",
        "views/webclient_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": ["binaural_appointment/static/src/js/appointment_form.js"],
    },
    "images": ["static/description/icon.png"],
    "application": True,
    "binaural":True,
}
