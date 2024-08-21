##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Sitaram Solutions (<https://sitaramsolutions.in/>).
#
#    For Module Support : info@sitaramsolutions.in  or Skype : contact.hiren1188
#
##############################################################################

{
    'name': 'Discount Limit Per Users',
    'version': "17.0.1.0.0",
    'category': 'Extra Addons',
    "license": "OPL-1",
    'summary': 'This app will helps you to set discount limit per users.',
    'description': """
        set discount limit
        user discount limit
        limited discount
        discount limit odoo apps
        how to limit for discount per user
        give restriction for giving discount per user
        discount restriction
        limit for the giving discount
        limit sales discount
        product discount limit
""",
    "price": 0,
    "currency": 'EUR',
    'author': 'Sitaram',
    'depends': ['base','sale_management','account'],
    'data': [
             'views/sr_inherit_users.xml',
    ],
    'website':"https://sitaramsolutions.in",
    'installable': True,
    'auto_install': False,
    'live_test_url':'https://youtu.be/FuM_dusdtd8',
    "images":['static/description/banner.png'],
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
