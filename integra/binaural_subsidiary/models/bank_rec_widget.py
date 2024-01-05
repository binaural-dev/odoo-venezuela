from odoo import models


class BankRecWidget(models.Model):
    _inherit = "bank.rec.widget"

    def button_validate(self, async_action=False):
        res = super(BankRecWidget, self).button_validate(async_action)
        self.move_id.line_ids._distribute_subsidiaries_analytic_accounts(True)
        return res
