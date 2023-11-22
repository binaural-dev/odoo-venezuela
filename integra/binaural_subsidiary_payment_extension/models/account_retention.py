from odoo import models
import logging

_logger = logging.getLogger(__name__)


class AccountRetention(models.Model):
    _inherit = "account.retention"

    def action_post(self):
        _logger.warning("action_post")
        res = super().action_post()
        for line in self.mapped("retention_line_ids"):
            _logger.warning(
                "line.move_id.account_analytic_id.id: %s", line.move_id.account_analytic_id.id
            )
            line.payment_id.write({"account_analytic_id": line.move_id.account_analytic_id.id})
        return res
