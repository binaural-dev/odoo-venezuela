{
    "name": "Venezuela - POS MF Self Order / Kiosk (Fiscal Machine)",
    "summary": """
        Impresión en máquina fiscal (TFHKA, Web Serial) para el Kiosko/Autopedido
        de pos_self_order, reutilizando el driver y la lógica de l10n_ve_pos_mf.
        Imprime la factura fiscal en local al confirmar la orden, de forma
        resiliente al servidor (imprimir-primero, sincronizar-después).
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Point of Sale",
    "version": "19.0.1.0.0",
    "depends": [
        # Driver Web Serial de la máquina fiscal (TfhkaDriver): se importa y se
        # inyecta directamente en el bundle del Kiosko, así que se declara como
        # dependencia DIRECTA (no solo transitiva vía l10n_ve_pos_mf).
        "l10n_ve_mf_base",
        # Máquina fiscal del POS de caja: aporta el server-side fiscal
        # (mf_invoice_number, _prepare_invoice_vals, write_mf_invoice_data).
        "l10n_ve_pos_mf",
        # Kiosko venezolano: identificación por cédula + factura forzada +
        # totales foráneos en el kiosko (precondición de la factura fiscal).
        "l10n_ve_pos_self_order",
    ],
    "assets": {
        "pos_self_order.assets": [
            # Driver Web Serial reutilizado TAL CUAL desde l10n_ve_mf_base
            # (autocontenido: solo depende de navigator.serial). Mismo patrón
            # que l10n_ve_pos_mf lo inyecta en point_of_sale._assets_pos.
            "l10n_ve_mf_base/static/src/core/*.js",
            "l10n_ve_mf_base/static/src/drivers/*.js",
            # Puente del kiosko: conexión al puerto, armado del payload y
            # enganche imprimir-primero/sincronizar-después.
            "l10n_ve_pos_mf_self_order/static/src/**/*",
        ],
    },
    "auto_install": True,
    "application": True,
    "images": ["static/description/icon.png"],
    "binaural": True,
}
