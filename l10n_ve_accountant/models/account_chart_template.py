import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    def _load(self, template_code, company, install_demo, force_create=True):
        res = super()._load(template_code, company, install_demo, force_create=force_create)
        # The constraint on `l10n_ve_use_foreign_exchange_diff` is skipped
        # while the chart loads (its config is written in separate steps),
        # so validate it once the load finishes: a chart that did not set
        # the exchange journal/accounts cannot keep the (default) flag on.
        company = company.sudo()
        if company.l10n_ve_use_foreign_exchange_diff:
            missing = company._l10n_ve_foreign_exchange_diff_missing_config()
            if missing:
                _logger.warning(
                    "Chart template %s left company %s without %s: disabling "
                    "'Use Alternate Currency Exchange Difference'.",
                    template_code, company.display_name, ", ".join(missing),
                )
                company.with_context(l10n_ve_skip_exchange_diff_check=True).l10n_ve_use_foreign_exchange_diff = False
        return res
