{
    "name": "Venezuela - Impuestos",
    "summary": "Impuestos para la localización en Venezuela",
    "description": """
Propósito
---------
Corrige el cálculo del alterno (moneda extranjera) del widget de totales
de impuestos (``tax_totals``) para que siempre coincida con el monto real
que verá el usuario en el wizard de pago o en la factura/orden posteada,
en vez de recalcularse de forma independiente y arrastrar unos centavos
de diferencia. Ticket: https://binaural.odoo.com/odoo/helpdesk.ticket/14463

Funcionalidades principales
---------------------------
* El widget de totales alternos (factura, cotización, orden de compra) se
  sincroniza contra los apuntes reales del asiento en vez de recalcular
  el impuesto de forma independiente por producto.
* Reparto determinístico de centavos de redondeo entre grupos de impuesto
  mediante el método del "mayor residuo" (largest remainder), reemplazando
  el prorrateo proporcional anterior.
* Manejo correcto de líneas con signo mixto (p. ej. descuentos negativos)
  en la base y el impuesto alterno, evitando que se sumen como si fueran
  siempre positivas.
* Anclaje del total alterno de cotizaciones (`sale.order`) y órdenes de
  compra (`purchase.order`) a `amount_total x tasa`, igual que en las
  facturas, para que no cambie al convertirse en factura/bill.

Cambios en UI / Modelos impactados
------------------------------------
* Modifica ``account.tax._prepare_tax_totals`` (nuevos métodos
  ``_sync_foreign_taxes_with_entry``, ``_anchor_foreign_taxes_for_order``,
  ``_finalize_foreign_taxes``, ``_apportion_largest_remainder``).
* No se agregan campos ni vistas nuevas.
""",
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Localizations/Account Chart",
    "version": "17.0.1.0.2",
    # any module necessary for this one to work correctly
    "depends": ["base", "account", "l10n_ve_base", "l10n_ve_rate"],
    "data": [
        "views/res_config_settings.xml",
        "views/account_move.xml",
        "views/account_journal.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "assets": {
        "web.assets_backend": ["l10n_ve_tax/static/src/components/**/*"],
    },
}
