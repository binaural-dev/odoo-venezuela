{
    "name": "Venezuela - Localización",
    "summary": "Modelos de ciudades, municipios y parroquias de Venezuela.",
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "17.0.0.0.2",
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
    "pre_init_hook": "pre_init_hook"
}
