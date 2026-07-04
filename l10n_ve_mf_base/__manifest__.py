{
    "name": "Venezuela - Máquina Fiscal (Base Web Serial)",
    "summary": "Driver base Web Serial API para impresoras fiscales The Factory HKA (TFHKA).",
    "description": """
        Capa técnica compartida para la comunicación con máquinas fiscales
        The Factory HKA vía Web Serial API (sin IoT Box).

        Contiene:
        - SerialConnection: transporte Web Serial.
        - FiscalProtocol / StatusParser: protocolo y estados TFHKA.
        - TfhkaDriver: driver de alto nivel (factura, NC, ND, reimpresión, X, Z).

        Es consumido por:
        - l10n_ve_pos_mf (Punto de Venta)
        - l10n_ve_iot_mf (Facturación/Contabilidad)
    """,
    "license": "LGPL-3",
    "category": "Accounting",
    "version": "17.0.1.0.0",
    "author": "binaural-dev",
    "website": "https://binauraldev.com",
    "depends": ["web"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_mf_base/static/src/core/*.js",
            "l10n_ve_mf_base/static/src/drivers/*.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
