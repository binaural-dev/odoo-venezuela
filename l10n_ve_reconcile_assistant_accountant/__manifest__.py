{
    "name": "Venezuela - Asistente de Conciliación (Contabilidad)",
    "summary": "El botón Reconciliar de la conciliación manual abre el asistente de conciliación "
               "cuando la selección es un pago o anticipo contra facturas.",
    "license": "LGPL-3",
    "description": """
    Pegamento entre `l10n_ve_reconcile_assistant` y `account_accountant` (Enterprise).
    Sustituye `account.move.line.action_reconcile`: si la selección es de las que el asistente
    maneja (pago o anticipo contra facturas, o una combinación que debe bloquearse con explicación)
    abre el asistente; cualquier otra selección sigue por la conciliación nativa.
    """,
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "19.0.1.0.0",
    "depends": [
        "l10n_ve_reconcile_assistant",
        "account_accountant",
    ],
    "data": [],
    "application": False,
    "auto_install": True,
    "installable": True,
}
