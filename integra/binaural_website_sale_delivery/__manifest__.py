{
    "name": "Binaural Website Sale Delivery",
    "summary": """
        Modulo para Actualizar la moneda alterna en el total de /shop/checkout
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Website",
    "version": "16.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": ['binaural_website_sale', "website_sale_delivery"],
    "data": [],
    'assets': {
        'web.assets_frontend': [
            'binaural_website_sale_delivery/static/src/**/*',
        ],
    },
    'auto_install': True,
    "application": True,
}
