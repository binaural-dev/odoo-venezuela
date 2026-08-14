{
    "name": "Binaural - Monto de Pago con IVA a Tasa de Factura",
    "summary": "El monto sugerido del wizard de pagos cobra el IVA a la tasa de la factura y la base imponible a la tasa del pago.",
    "description": """
        En el asistente de registro de pago (account.payment.register), el
        monto sugerido por defecto ahora se calcula tratando el IVA de la
        factura como congelado a la tasa propia de la factura
        (account.move.foreign_rate) y la base imponible a la tasa vigente del
        pago (fecha/moneda/diario elegidos en el wizard). Se recalcula en
        vivo al cambiar la fecha, la moneda o el diario.

        Ese monto sugerido paga deliberadamente menos que una conversión
        simple a una sola tasa (esa es la protección al IVA) - por eso el
        módulo también configura automáticamente el mecanismo nativo de
        Odoo "Mark as fully paid" con la cuenta de diferencial cambiario de
        la compañía, para que al confirmar el pago con ese monto la factura
        cierre sola (la diferencia se registra como ganancia/pérdida en
        cambio, igual que cualquier otro pago a una tasa distinta).

        Alcance: solo aplica cuando el wizard paga una única factura (o nota
        de crédito) cuya moneda es la moneda de la compañía o su
        foreign_currency_id. No aplica a pagos con IGTF ni a lotes
        multi-factura.
    """,
    "version": "19.0.1.0.0",
    "category": "Accounting",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "license": "LGPL-3",
    "depends": [
        "account",
        "l10n_ve_accountant",
    ],
    "data": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}
