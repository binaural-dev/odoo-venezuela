from odoo import models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _create_igtf_move_supplier_two_percentage(self):
        res = super()._create_igtf_move_supplier_two_percentage()
        res.button_draft()
        res.account_analytic_id = self.account_analytic_id.id
        res.action_post()
        return res
