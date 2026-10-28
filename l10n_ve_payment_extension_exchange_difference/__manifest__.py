{
    "name": "Venezuela - Retenciones con Diferencial Cambiario como Nota",
    "summary": """
        Puente entre Retenciones y el diferencial cambiario como notas de débito/crédito
    """,
    "description": """
    Venezuela - Retenciones con Diferencial Cambiario como Nota
    ===========================================================
    Se instala solo cuando están instalados `l10n_ve_payment_extension` (retenciones) y
    `l10n_ve_exchange_difference` (diferencial cambiario como notas), que no dependen uno del otro.

    Agrega al comprobante de retención indexada de cliente la opción "Nota de débito/crédito" para
    documentar su diferencial cambiario, además del asiento. El valor inicial sale de la
    configuración del cliente (si la compañía usa notas y el contacto las permite); se puede
    cambiar en cada comprobante.
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accountant/Accountant",
    "version": "19.0.1.0.0",
    "depends": [
        "l10n_ve_payment_extension",
        "l10n_ve_exchange_difference",
    ],
    "data": [],
    "application": False,
    "auto_install": True,
    "installable": True,
}
