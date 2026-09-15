{
    "name": "Venezuela - Ventas",
    "summary": "Módulo de Ventas Venezuela",
    "description": """
Propósito
---------
Adapta las cotizaciones y órdenes de venta a los requerimientos de la
localización venezolana: seguimiento del monto equivalente en moneda
alterna (extranjera), validaciones fiscales propias y ajustes al flujo
de facturación desde la orden.

Funcionalidades principales
---------------------------
* Tasa alterna de la cotización (manual o automática según la fecha) y
  cálculo del precio, subtotal y total equivalente en esa moneda para
  cada línea, anclado al total real del documento -- coincide con el de
  la factura resultante al confirmarse la orden.
* Validaciones: un único impuesto por línea de producto, y límite máximo
  de líneas por cotización.
* Base imponible y total facturado en moneda alterna (``foreign_taxable_income``,
  ``foreign_total_billed``) para reportes fiscales.
* Bloqueo de la confirmación de la orden bajo ciertas condiciones de
  negocio, y ajustes al listado de precios (``product.pricelist.item``).
* Reporte de documento de venta y tarea programada (cron) propios del
  módulo.

Cambios en UI / Modelos impactados
------------------------------------
* Modifica ``sale.order`` y ``sale.order.line`` (moneda alterna, tasa,
  ``foreign_price``, ``foreign_subtotal``) y ``product.pricelist.item``.
* Vistas de la orden de venta, ajustes de configuración y menús.
""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Sales/Sales",
    "version": "17.0.1.1.25",
    # any module necessary for this one to work correctly
    "depends": [
        "base",
        "l10n_ve_base",
        "l10n_ve_tax",
        "sale_management",
        "l10n_ve_rate",
        "l10n_ve_contact",
        "l10n_ve_invoice",
        "l10n_ve_filter_partner",
        "l10n_ve_stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/res_groups.xml",
        "data/ir_cron.xml",
        "report/report_sale_document.xml",
        "views/res_config_settings.xml",
        "views/sale_order.xml",
        "views/product_pricelist_item_views.xml",
        "views/menuitems.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "pre_init_hook": "pre_init_hook",
}
