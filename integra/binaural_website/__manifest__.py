{
    'name': "Binaural Sitio Web",

    'summary': """
       Modulo para sitio web""",

    'license': 'LGPL-3',
    
    'author': "Binauraldev",
    'website': "https://binauraldev.com/",
    'category': 'Website',

    # any module necessary for this one to work correctly
    'depends': ['base','website','binaural_location'],
    
    "data": [
        "static/src/views/profile_view.xml",
    ],
    
    "assets": {
        'web.assets_frontend': [
            'binaural_website/static/src/js/profile.js',
        ]
    },

    'application':True,
}