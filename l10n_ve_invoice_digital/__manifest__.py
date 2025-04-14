{
    "name": "Binaural Digital Invoice",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "17.0.0.0.0",
    "depends": [
        "base",
        "account",
        "l10n_ve_invoice",
    ],
    
    "images": ["static/description/icon.png"],
    "application": True,
    "data": [
        "views/res_config_settings.xml",
        "views/account_move_view.xml",
    ],
    
    "binaural": True,
}