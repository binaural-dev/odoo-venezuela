from odoo import api, fields, models, _, Command
import datetime
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    product_id = fields.Many2one(
        "product.product",
        string="Related Product",
        domain="[('is_appointment', '=', True),('sale_ok', '=', True)]",
    )

    time_limit = fields.Float(
        string='Time Limit (hours)',
        related='product_id.time_limit',
    )
    
    block_appointment = fields.Integer(
        string='Block Appointment',
        related='product_id.block_appointment',
    )

    start = fields.Datetime(
        string='start',
        
    )

    def _prepare_opportunity_quotation_context(self):
        quotation_context = super()._prepare_opportunity_quotation_context()

        if self.product_id:
            quotation_context['default_order_line'] = [(0, 0, {
                'product_id': self.product_id.id,
                'name': self.product_id.name + ' ' + self.start.strftime('%H:%M'),
                'product_uom_qty': 1,
                'product_uom': self.product_id.uom_id.id,
                'price_unit': self.product_id.lst_price,
            })]
        return quotation_context