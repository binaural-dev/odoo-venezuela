{
    "name": "Venezuela - Aplicación Parcial de Anticipos",
    "summary": "Permite aplicar un monto parcial de un anticipo o crédito pendiente desde el widget de pagos.",
    "description": """
        Base reutilizable del Motor transversal de aplicación parcial de pagos.

        Permite aplicar un monto PARCIAL de un anticipo o crédito pendiente
        desde el popover "Añadir" del widget de pagos, en vez de conciliar
        siempre el residual completo. Sobrescribe js_assign_outstanding_line
        de l10n_ve_igtf para leer el monto solicitado desde el contexto de la
        llamada, ajustarlo a lo que debe la factura y a lo que tiene
        disponible el anticipo, y encaminarlo a través de la conciliación y
        el mecanismo de IGTF ya existentes.

        No reimplementa el generador de asientos de anticipo, el cálculo de
        IGTF ni el motor de conciliación de Odoo -- solo alimenta un monto
        más chico y validado al mecanismo existente de
        l10n_ve_igtf/account. Sin un monto parcial en contexto, el
        comportamiento es idéntico al de l10n_ve_igtf sin modificar
        (conciliación del residual completo).

        Primer corte de base: cubre únicamente el punto de entrada del
        widget "Añadir" en factura. Registrar Pago, Conciliar Pagos,
        Asientos Contables, notas de crédito, configuración por compañía y
        permiso de seguridad quedan para tareas posteriores del Motor
        transversal.
    """,
    "license": "LGPL-3",
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "19.0.0.1.1",
    "images": ["static/description/icon.png"],
    "depends": [
        "l10n_ve_igtf",
        # Directly referenced (inherit_id) by views/res_config_settings.xml,
        # not just transitively available through l10n_ve_igtf.
        "l10n_ve_base",
    ],
    "data": [
        "security/res_groups.xml",
        "views/res_config_settings.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_partial_payment/static/src/scss/account_payment_field_partial.scss",
            "l10n_ve_partial_payment/static/src/js/account_payment_field_partial.js",
            "l10n_ve_partial_payment/static/src/xml/account_payment_templates.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
