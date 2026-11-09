{
    'name': 'Venezuela - Lista Negra de Correos Configurable',
    'summary': 'Blacklist email addresses after a configurable number of bounces/failures '
               'and block every outgoing email to blacklisted addresses',
    'version': '19.0.1.0.1',
    'category': 'Marketing/Email Marketing',
    'author': 'Binauraldev',
    'website': 'https://binauraldev.com/',
    'license': 'LGPL-3',
    'depends': ['mass_mailing'],
    'data': [
        'security/ir.model.access.csv',
        'views/mail_bounce_event_views.xml',
        'views/mail_bounce_event_menus.xml',
        'views/mail_blacklist_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    "application": False,
}
