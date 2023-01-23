{
    "name": "Binaural Localización",
    "description": """
        Maestros de ciudades, municipios
parroquias. 
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "1.0",
    "depends": ["base", "contacts"],
    "data": [
        "security/ir.model.access.csv",
        "data/res_country_state.xml",
        "data/res_country_municipality.xml",
        "data/res_country_parish.xml",
        "views/res_country_parish_views.xml",
        "views/res_country_municipality_views.xml",
        "views/res_country_city_views.xml",
        "views/menus.xml",
    ],
    "application": True,
}
