from odoo import models
import logging

_logger = logging.getLogger(__name__)

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _prepare_foreign_base_line_for_taxes_computation(self):
        """
        Convert the current record to a dictionary in order to use the generic taxes computation method
        defined on account.tax.

        :return: A python dictionary.
        """
        self.ensure_one()
        return self.env['account.tax']._prepare_foreign_base_line_for_taxes_computation(
            self,
            price_unit=self.foreign_price,
            tax_ids=self.taxes_id,
            quantity=self.product_qty,
            partner_id=self.order_id.partner_id,
            currency_id=self.order_id.foreign_currency_id,
            rate=self.foreign_inverse_rate,
        )
