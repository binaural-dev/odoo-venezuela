from odoo import models


class AccountRetention(models.Model):
    _inherit = "account.retention"

    def action_post(self):
        res = super().action_post()
        for line in self.mapped("retention_line_ids"):
            line.payment_id.write({"account_analytic_id": line.move_id.account_analytic_id.id})
        return res
