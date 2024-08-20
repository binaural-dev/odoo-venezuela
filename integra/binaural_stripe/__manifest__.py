# -*- coding: utf-8 -*-
{
    'name': "Binaural Stripe",

    'summary': """
        Modulo agregar Venezuela a Stripe""",

    'description': """
        Este modulo permite agregar Venezuela a Stripe, eliminando la restriccion por defecto que trae en el nativo (podria no funcionar en funcion
        de lo que defina Stripe en su politica de uso)
    """,

    'author': "Binaural C.A.",
    "license": "LGPL-3",
    'website': "https://www.binauraldev.com",
    "binaural": True,

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Accounting/Payment Providers',
    'version': '16.0.0.2',

    # any module necessary for this one to work correctly
    'depends': ['payment_stripe'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',        
    ],
    'assets': {
        'web.assets_frontend': [
            'binaural_stripe/static/src/js/express_checkout_form.js',            
        ],
    },
    # only loaded in demonstration mode
}
