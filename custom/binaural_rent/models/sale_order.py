from odoo import models, _
from odoo.exceptions import  ValidationError

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    def action_confirm(self):
        res = super().action_confirm()
        for order_line in self.order_line:
            rental_schedules = self.env['sale.rental.schedule'].search([
                ('product_id', '=', order_line.product_id.id),
                ('return_date', '>=', order_line.start_date),
                ('pickup_date', '<=', order_line.return_date),
            ])
            for rental_schedule in rental_schedules:
                if rental_schedule.order_line_id.id != order_line.id:
                    raise ValidationError(_("The rental cannot be confirmed due to a schedule conflict"))
        return res 