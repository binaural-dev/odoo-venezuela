{
    "name": "Cadipa Calendario de Reservas",
    "summary": """
        Modulo para Agregar el calendio de reservas.
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "",
    "version": "17.0.1.0.0",
    "depends": [
        "website", "appointment",
    ],
    "data": [
        "views/reservation_calendar.xml",
        "views/appointment_type.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "cadipa_reservation_calendar/static/src/css/reservation_calendar.css",
            "cadipa_reservation_calendar/static/src/js/reservation_calendar.js",
        ]
    },
    "images": ["static/description/icon.png"],
    "application": True,
}
