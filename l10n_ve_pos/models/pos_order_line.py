from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)

class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    foreign_price = fields.Float(string="Foreign Price",digits=0)
    foreign_subtotal = fields.Float(string="Foreign Subtotal", digits=0)
    foreign_total = fields.Float(string="Foreign Total", digits=0)

    @api.model
    def _load_pos_data_fields(self, config_id):
        res = super()._load_pos_data_fields(config_id)
        res += ['foreign_price', 'foreign_subtotal', 'foreign_total']
        return res