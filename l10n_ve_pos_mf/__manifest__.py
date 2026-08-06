{
    "name": "Venezuela - Integración de Punto de Venta con Maquina Fiscal",
    "version": "19.0.3.0.0",
    "category": "Accounting",
    "summary": "Venezuela - Integración de Punto de Venta con Maquina Fiscal (Web Serial API)",
    "sequence": "1",
    "license": "LGPL-3",
    "author": "Binaural",
    "support": "contacto@binaural.dev",
    "depends": [
        "point_of_sale",
        "l10n_ve_pos",
        "l10n_ve_mf_base",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/res_group.xml",
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
            # Driver Web Serial compartido (l10n_ve_mf_base)
            "l10n_ve_mf_base/static/src/core/*.js",
            "l10n_ve_mf_base/static/src/drivers/*.js",
            # Módulo POS
            "l10n_ve_pos_mf/static/src/utils/*.js",
            "l10n_ve_pos_mf/static/src/overrides/DevicesSynchronisation.js",
            "l10n_ve_pos_mf/static/src/overrides/*.js",
            "l10n_ve_pos_mf/static/src/components/**/*.js",
            "l10n_ve_pos_mf/static/src/js/*.js",
            # Templates y CSS
            "l10n_ve_pos_mf/static/src/xml/*.xml",
            "l10n_ve_pos_mf/static/src/components/**/*.xml",
            "l10n_ve_pos_mf/static/src/css/*.css",
        ],
    },
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": False,
    "auto_install": False,
    "binaural": True,
}
