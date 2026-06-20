{
    "name": "Venezuela - Integración de Punto de Venta con Maquina Fiscal",
    "version": "17.0.2.0.0",
    "category": "Accounting",
    "summary": "Venezuela - Integración de Punto de Venta con Maquina Fiscal",
    "description": "Venezuela - Integración de Punto de Venta con Maquina Fiscal",
    "sequence": "1",
    "license": "LGPL-3",
    "author": "Binaural.dev",
    "support": "contacto@binaural.dev",
    "depends": [
        "point_of_sale",
        "l10n_ve_pos",
        # DEPRECATED: Eliminamos dependencias del IoT Box (ahora usamos Web Serial API)
        # "pos_iot",
        # "l10n_ve_iot_mf",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/pos_config.xml",
        "views/pos_order.xml",
        "views/pos_session.xml",
        "views/account_move.xml",
        "views/account_tax.xml",
        "views/pos_payment_method.xml",
        "wizard/wizard_sales_book.xml",
        "views/res_config_settings.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            # Nueva arquitectura Web Serial API
            "l10n_ve_pos_mf/static/src/core/*.js",
            "l10n_ve_pos_mf/static/src/drivers/*.js",
            "l10n_ve_pos_mf/static/src/utils/*.js",
            "l10n_ve_pos_mf/static/src/overrides/*.js",
            "l10n_ve_pos_mf/static/src/components/**/*.js",
            
            # Archivos legacy (mantenemos temporalmente por compatibilidad)
            "l10n_ve_pos_mf/static/src/js/ReprintInvoiceButton.js",
            "l10n_ve_pos_mf/static/src/js/ClosePosPopup.js",
            # "l10n_ve_pos_mf/static/src/js/DebugWidget.js", # DEPRECATED: Consolidado en overrides/DebugWidget.js
            "l10n_ve_pos_mf/static/src/js/OrderState.js",
            
            # Templates y CSS
            "l10n_ve_pos_mf/static/src/xml/*.xml",
            "l10n_ve_pos_mf/static/src/components/**/*.xml",
            "l10n_ve_pos_mf/static/src/css/*.css",
        ],
        "web.qunit_suite_tests": [
            # Tests QUnit para el driver TFHKA
            "l10n_ve_pos_mf/static/src/tests/*.js",
        ],
    },
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": False,
    "auto_install": False,
    "binaural": True,
}
