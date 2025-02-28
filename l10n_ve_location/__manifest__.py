{
    "name": "Venezuela - localization",
    "summary": """
        Masters of cities, municipalities, and parishes.
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "17.0.1.0.2",
    "depends": ["base", "contacts"],
    "data": [
        "security/ir.model.access.csv",
        "data/res_country_state_data.xml",
        "data/res_country_municipality_data.xml",
        "data/res_country_parish_data.xml",
        "views/res_country_parish_views.xml",
        "views/res_country_municipality_views.xml",
        "views/res_country_city_views.xml",
        "views/res_partner_views.xml",
        "views/menus.xml",
    ],
    "application": True,
    "binaural": True,
}
