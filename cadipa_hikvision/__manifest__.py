{
    'name': 'Hikvision Cadipa Integration',
    'version': '17.0.1.0.1',
    'summary': '',
    'author': 'Binaural',
    'depends': [
        'base',
        'website',
        'bus',
        'cadipa_appointment',
        'calendar',
        'mail',
        'binaural_hikvision_employee',
    ],
    'data': [
        'data/mail_template.xml',
        'views/calendar_view.xml',
        'views/hikcentral_user.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'cadipa_hikvision/static/src/xml/access_status_screen.xml',
            'cadipa_hikvision/static/src/js/access_status_screen.js',
            'cadipa_hikvision/static/src/js/guest_resend_email.js',
            'cadipa_hikvision/static/src/js/appointment_guest_delete.js',
        ],
    },
    'installable': True,
    'application': True,
}