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
    "version": "17.0.0.0.0",
    # Depends on l10n_ve_currency_rate_live to reuse `can_update_habil_days`
    # and `_is_valid_rate_date` (the decision of whether an advance rate for
    # the next business day applies already lives there, not reimplemented).
    "depends": ["l10n_ve_currency_rate_live"],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_data.xml",
        "wizard/bcv_sync_api_key_wizard.xml",
        "views/res_config_settings.xml",
    ],
}
