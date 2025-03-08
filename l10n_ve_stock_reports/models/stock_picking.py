from odoo import _, fields, models,api

import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = "stock.picking"

    payment_term = fields.Many2one(
        comodel_name='account.payment.term',
        related='sale_id.payment_term_id',
        readonly=True,
    )

    show_button = fields.Boolean(compute="_compute_show_button",default=False)
    
    @api.depends("payment_term")
    def _compute_show_button(self):
        for picking in self:

            picking.show_button = False

            if  picking.payment_term:
                for line in picking.payment_term.line_ids:
                    if line.value == "balance" and line.days > 0:
                        picking.show_button = True
                        break

    def accion_personalizada(self):
        _logger.info(f"MOVE LINES DEL PICKING:{self.move_ids.read([])}")