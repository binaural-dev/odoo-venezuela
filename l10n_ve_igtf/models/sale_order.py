from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    foreign_inverse_rate = fields.Float(
        string="Foreign Inverse Rate",
        compute="_compute_foreign_inverse_rate",
        store=True,
        default=1.0,
    )

    @api.depends('currency_id', 'date_order', 'company_id')
    def _compute_foreign_inverse_rate(self):
        for order in self:
            date = order.date_order or fields.Date.today()
            if order.currency_id and order.company_id and order.currency_id != order.company_id.currency_id:
                order.foreign_inverse_rate = order.currency_id.with_context(date=date).compute(1.0, order.company_id.currency_id)
            else:
                order.foreign_inverse_rate = 1.0