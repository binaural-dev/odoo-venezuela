{
    "name": "Venezuela - IGTF",
    "summary": "Módulo para campos del impuesto IGTF (Impuesto a las grandes transacciones financieras)",
    "description": """
Propósito
---------
Implementa el IGTF (Impuesto a las Grandes Transacciones Financieras):
el recargo aplicado a los pagos realizados en moneda extranjera (o desde
cuentas en divisas) según la normativa venezolana.

Funcionalidades principales
---------------------------
* Cálculo del IGTF sobre el monto de un pago en moneda extranjera,
  usando la tasa de la fecha del pago o de la factura según
  configuración, con utilidades compartidas (``l10n_ve_igtf.utils``).
* Configuración por compañía: porcentaje del IGTF, cuentas contables de
  IGTF por cliente/proveedor, y opciones para mostrar/ocultar la base
  imponible del IGTF en ventas y compras.
* Integración con el wizard de registro de pagos para sugerir y aplicar
  el IGTF automáticamente, y con el reporte de factura de forma libre.
* Marcado de diarios sujetos a IGTF.

Cambios en UI / Modelos impactados
------------------------------------
* Modifica ``account.journal``, ``account.move``, ``account.payment``,
  ``account.tax``, ``res.company`` y ``res.partner``; agrega el modelo
  abstracto ``l10n_ve_igtf.utils``.
* Vistas del diario contable, ajustes de configuración, wizard de
  registro de pagos y reporte de factura de forma libre.
""",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "17.0.1.0.3",
        "depends": [
        "base",
        "l10n_ve_accountant",
        "l10n_ve_rate",
        "l10n_ve_tax",
        "l10n_ve_invoice",
        "l10n_ve_tax_payer",
    ],
       
    
    "data": [
        "views/account_journal.xml",
        "views/res_config_settings.xml",
        "report/invoice_free_form.xml",
        "wizard/account_payment_register.xml",
    ],
    "images": ["static/description/icon.png"],
    "assets": {
        "web.assets_backend": ["l10n_ve_igtf/static/src/components/**/*"],
    },
    "pre_init_hook": "pre_init_hook",
    "application": True,
}
