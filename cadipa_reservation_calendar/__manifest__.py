{
    "name": "Cadipa Calendario de Reservas",
    "summary": "Módulo para agregar el calendario de reservas.",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Website/Website",
    "version": "17.0.1.0.13",
    "depends": [
        "website",
        "appointment",
    ],
    "data": [
        "data/security.xml",
        "views/reservation_calendar.xml",
        "views/appointment_type.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "cadipa_reservation_calendar/static/src/css/*.css",
            "cadipa_reservation_calendar/static/src/**/*",
            
        ],
    },
    "images": ["static/description/icon.png"],
    "application": True,
}
