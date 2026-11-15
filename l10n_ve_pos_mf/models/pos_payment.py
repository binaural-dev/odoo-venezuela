from odoo import models


class PosPayment(models.Model):
    _inherit = "pos.payment"

    def _get_fiscal_code(self):
        """Fiscal printer code of the payment: the one of its method for the
        currency the customer paid with."""
        self.ensure_one()
        return self.payment_method_id._get_fiscal_code(self.payment_currency_id)
