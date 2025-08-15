from odoo import models

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _prepare_foreign_base_line_for_taxes_computation(self):
        """ Convert the current record to a dictionary in order to use the generic taxes computation method
        defined on account.tax.

        :return: A python dictionary.
        """
        self.ensure_one()
        return self.env['account.tax']._prepare_foreign_base_line_for_taxes_computation(
            price_unit=self.foreign_price,
            tax_ids=self.tax_id,
            quantity=self.product_uom_qty,
            partner_id=self.order_id.partner_id,
            currency_id=self.order_id.currency_id or self.order_id.company_id.currency_id,
            rate=getattr(self.order_id, 'currency_rate', 1.0),
        )
