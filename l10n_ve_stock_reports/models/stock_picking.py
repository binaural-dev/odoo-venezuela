from odoo import _, fields, models,api

import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = "stock.picking"

    payment_term = fields.Many2one(
        comodel_name='account.payment.term',
        related='sale_id.payment_term_id',
        readonly=True,
        # compute="_compute_payment_term",
    )

    # delivery_order_number = fields.

    # show_payment_term = fields.Boolean(compute="_compute_show_payment_term",default=False)
    show_button = fields.Boolean(compute="_compute_show_button",default=False)

    # @api.depends("picking_type_id")
    # def _compute_show_payment_term(self):
    #     for picking in self:
    #         if not picking.picking_type_id:
    #             picking.show_payment_term = False
    #             continue

    #         if picking.picking_type_id.code != "outgoing":
    #             picking.show_payment_term = False
    #             continue

    #         if not picking.payment_term:
    #             picking.show_payment_term = False
    #             continue
    #         picking.show_payment_term = True
    
    @api.depends("payment_term")
    def _compute_show_button(self):
        for picking in self:

            # Asigna un valor por defecto en todos los casos
            picking.show_button = False

            if  picking.payment_term:
                for line in picking.payment_term.line_ids:
                    if line.value == "balance" and line.days > 0:
                        picking.show_button = True
                        break


    # @api.depends("sale_id.payment_term_id")
    # def _compute_payment_term(self):
    #     for picking in self:
    #         picking.payment_term = picking.sale_id.payment_term_id if picking.sale_id else False

    def accion_personalizada(self):
        _logger.info(f"TIPO DE OPERACION:{self.picking_type_id.code}")