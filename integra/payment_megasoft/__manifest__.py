
{
    'name': 'Payment Provider: Megasoft',
    'version': '16.0.0.1.3',
    'sequence': 350,
    'category': 'Accounting/Payment Providers',
    'summary': "Este modulo permite habilitar un nuevo metodo de pago con Megasoft.",
    'depends': ['payment'],
    'external_dependencies': {
        'python': ['xmltodict']
    },
    'data': [
        'views/payment_provider.xml',
        "views/payment_megasoft_templates.xml",
        "views/get_payment.xml",
        "views/payment_portal_templates.xml",
        'data/payment_provider_data.xml',
    ],
    'application': False,
    'assets': {
        'web.assets_frontend': [
            # 'payment_megasoft/static/src/css/megasoft.css', es para no perder el disenio de la pagina de megasoft, es plantilla para mandarlo a ellos
            'payment_megasoft/static/src/js/payment_form.js',
            # 'payment_megasoft/static/src/js/post_processing.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
}
