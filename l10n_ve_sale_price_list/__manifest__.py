{
    "name": "Venezuela - Reporte de Lista de Precios Multi-Lista",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "summary": "Reporte de lista de precios con varias listas en columnas, "
    "por compañía/sucursal, con paginación",
    "description": """
        Extiende el reporte nativo "Imprimir lista de precios" de Odoo para
        mostrar varias listas de precios en columnas (en vez de una sola
        lista con varias cantidades), permitiendo agregar/quitar listas
        dinámicamente. Al abrir el reporte se precargan por defecto las
        listas de precio de la compañía activa del usuario (más las que no
        tienen compañía asignada). La vista en pantalla pagina de 20 en 20
        productos para que catálogos grandes no tarden en cargar; la
        exportación a PDF siempre incluye todos los productos
        seleccionados, sin paginar. El nombre de cada lista de precios
        muestra su compañía entre paréntesis para identificarla en
        entornos multi-sucursal.

        Ver README.rst para el detalle de configuración por sucursal.
    """,
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Sales",
    "depends": ["product"],
    "data": [
        "security/res_groups.xml",
        "report/product_pricelist_report_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_sale_price_list/static/src/js/pricelist_report/product_pricelist_report.js",
            "l10n_ve_sale_price_list/static/src/js/pricelist_report/product_pricelist_report.xml",
        ],
    },
    "images": ["static/description/icon.png"],
    "application": False,
}
