from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def reconcile(self):
        res = super().reconcile()
        lines = self
        lines_with_statements = self.env["account.move.line"]
        for line in lines:
            if line.statement_line_id:
                lines_with_statements |= line
        lines -= lines_with_statements
        lines_with_statements.analytic_distribution = lines[0].analytic_distribution
        return res

