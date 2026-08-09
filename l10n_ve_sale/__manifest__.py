{
    "name": "Venezuela - Ventas",
    "summary": "Módulo de Ventas Venezuela",
    "description": """
Propósito
---------
Corrige el cálculo del alterno (moneda extranjera) en cotizaciones de
venta para que el total mostrado coincida con el de la factura resultante
al confirmarse. Ticket: https://binaural.odoo.com/odoo/helpdesk.ticket/14463

Funcionalidades principales
---------------------------
* El total alterno de la cotización se ancla a `amount_total x tasa` (el
  mismo mecanismo que usan las facturas en l10n_ve_accountant/l10n_ve_tax),
  en vez de recalcularse de forma independiente por línea.
* Corrección de precisión del precio unitario alterno (`foreign_price`),
  que antes se truncaba a 2 decimales.
* El cálculo del alterno delega en `res.currency._convert` (igual que
  account.move.line), respetando correctamente la conversión cuando la
  moneda base de la compañía es USD.
* El subtotal alterno de la línea ahora considera el impuesto asignado
  (`tax_id`), en vez de ignorarlo.

Cambios en UI / Modelos impactados
------------------------------------
* Modifica ``sale.order.line`` (``foreign_price``, ``_compute_foreign_price``,
  ``_compute_foreign_subtotal``).
* No se agregan campos ni vistas nuevas.
""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Sales/Sales",
    "version": "17.0.1.1.24",
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
