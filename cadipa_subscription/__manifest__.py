{
    "name": "Cadipa Suscripciones",
    "summary": """
       Modulo para personalizaciones de suscripciones de CADIPA """,
    "version": "17.0.1.0.0",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Subscription",
    # any module necessary for this one to work correctly
    "depends": [
        "cadipa_appointment",
        "binaural_appointment",
        "web",
        "web_gantt",
    ],
    # always loaded
    "data": [
        "views/sale_subscription_plan_views.xml",
        "views/subscription_payment_preview.xml"
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}
