{
    "name": "Venezuela - Asistente de Conciliación",
    "summary": "Asistente que concilia un pago o anticipo contra una o varias facturas con las "
               "mismas reglas del widget de la factura (fecha de conversión, tasa, IGTF y cruce de "
               "anticipo).",
    "license": "LGPL-3",
    "description": """
    Venezuela - Asistente de Conciliación
    =====================================
    La conciliación manual nativa no pasa por las reglas de `l10n_ve_igtf` (cruce de anticipo,
    IGTF y tasas del widget). Este módulo clasifica la selección de líneas y, si es un pago o un
    anticipo contra una o varias facturas, la aplica factura por factura con
    `js_assign_outstanding_line`, en el orden que elija el usuario, leyendo el widget de nuevo
    antes de cada par y en una sola transacción. Las combinaciones que romperían el vínculo con el
    pago origen (líneas de cruce, notas, anticipo contra otra cuenta, socios o compañías distintos,
    más de un origen) se bloquean con la explicación.

    El módulo no depende de Enterprise: el botón "Reconciliar" de la conciliación manual se
    sustituye en `l10n_ve_reconcile_assistant_accountant`.
    """,
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "19.0.1.0.1",
    "depends": [
        "l10n_ve_igtf",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizard/l10n_ve_reconcile_assistant_views.xml",
    ],
    "application": False,
    "auto_install": False,
    "installable": True,
}
