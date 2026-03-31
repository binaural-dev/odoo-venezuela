from odoo import models, api, fields


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _prepare_account_move_line(self, move=False):
        """
        Override the account move line to use the price total instead of the price unit discounted.
        This fix ensures proper rounding to avoid precision residues (example, 0.0005) 
        that cause unbalanced move errors.
        """
        res = super()._prepare_account_move_line(move=move)
        if 'balance' not in res:
            total_wo_tax = self.price_total
            res['balance'] = self.currency_id._convert(
                total_wo_tax,
                self.company_id.currency_id,
                self.company_id,
                self.order_id.date_order or fields.Date.today(),
                round=True,
            )
        return res
