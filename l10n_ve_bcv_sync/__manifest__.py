{
    "name": "Venezuela - BCV Sync (Receptor de tasas)",
    "summary": """
        Endpoint HTTP que recibe, via POST autenticado, las tasas oficiales
        del BCV publicadas por el servicio externo BCV Sync.
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Technical",
    "version": "17.0.0.0.1",
    # Depends on l10n_ve_currency_rate_live only to reuse the
    # `can_update_habil_days` field on res.company. The date-validity
    # decision itself is fully self-contained in this module (see
    # `res.company._bcv_sync_is_valid_rate_date`), it does not call
    # l10n_ve_currency_rate_live's own `_is_valid_rate_date`.
    "depends": ["l10n_ve_currency_rate_live"],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_data.xml",
        "wizard/bcv_sync_api_key_wizard.xml",
        "views/res_config_settings.xml",
    ],
}
