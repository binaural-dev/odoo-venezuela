{
    "name": "Venezuela - Impuestos",
    "summary": "Impuestos para la localización en Venezuela",
    "description": """
Propósito
---------
Provee la configuración e infraestructura de impuestos de la
localización venezolana: define las alícuotas de IVA (general, reducida,
exenta, extendida) usadas en ventas y compras -- nacionales e
internacionales -- y extiende el widget de totales de impuestos para
mostrar, junto al monto en moneda base, su equivalente en la moneda
alterna configurada en la compañía.

Funcionalidades principales
---------------------------
* Configuración por compañía de la cuenta/impuesto asociado a cada
  alícuota (general/reducida/exenta/extendida) para ventas y compras,
  con variantes específicas para operaciones internacionales.
* Marcado de diarios de compra/venta como "internacionales" (un único
  diario internacional de compra permitido por compañía) para uso en
  reportes fiscales.
* Widget de totales de impuestos (``tax_totals``) extendido con el
  desglose y el total equivalente en la moneda alterna de la compañía,
  anclado a los apuntes reales del asiento contable (o al total del
  documento en cotizaciones y órdenes de compra) para que siempre
  coincida con el monto que verá el usuario en el wizard de pago.
* Opción para exigir que cada línea de factura tenga un único impuesto
  asociado.

Cambios en UI / Modelos impactados
------------------------------------
* Modifica ``account.tax`` (``_prepare_tax_totals`` y su lógica de
  sincronización del alterno), ``account.journal``
  (``is_sale_international``, ``is_purchase_international``) y
  ``res.company`` (alícuotas configurables por tipo de operación).
* Vistas de ajustes de configuración, diario contable y asiento.
""",
    "license": "LGPL-3",
    "author": "Binauraldev",
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
