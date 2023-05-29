{
    'name': "Binaural Sitio Web",

    'summary': """
       Modulo para sitio web""",

    'license': 'LGPL-3',
    
    'author': "Binauraldev",
    'website': "https://binauraldev.com/",
    'category': 'Website',
    'version': '0.2.0',
    # any module necessary for this one to work correctly
    'depends': ['base','website','binaural_location','website_sale'],
    
    "data": [
        "static/src/views/profile_view.xml",
        "static/src/views/website_sale_view.xml",
    ],
    
    "assets": {
        'web.assets_frontend': [
            'binaural_website/static/src/js/profile.js',
            'binaural_website/static/src/js/website_sale.js'
        ]
    },

    'application':True,
}