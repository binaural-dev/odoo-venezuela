from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_get_retention_lines(self):
        _logger.warning(
            "Retention Lines %s",
            self.env["account.retention"].compute_retention_lines_data(
                self.partner_id, self, ("iva", "in_invoice")
            ),
        )
