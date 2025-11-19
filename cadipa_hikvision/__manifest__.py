{
    'name': 'Hikvision Cadipa Integration',
    'version': '17.0.1.0.0',
    'summary': '',
    'author': 'Binaural',
    'depends': [
        'base',
        'website',
        'bus',
        'cadipa_appointment',
        'mail',
        'binaural_hikvision_employee',
    ],
    'data': [
        'data/mail_template.xml',
        'views/hikcentral_users.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'cadipa_hikvision/static/src/xml/access_status_screen.xml',
            'cadipa_hikvision/static/src/js/access_status_screen.js',
        ],
    },
    'installable': True,
    'application': True,
}