from odoo import models, fields, api, _

import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    seller_id = fields.Many2one(
        "hr.employee",
        string="Seller",
        help="Partner's seller reference.",
        domain=[("is_seller", "=", True)],
    )

    @api.model
    def _order_fields(self, ui_order):
        res = super()._order_fields(ui_order)
        res["seller_id"] = ui_order["seller_id"]
        return res

    def _prepare_invoice_vals(self):
        self.ensure_one()
        res = super()._prepare_invoice_vals()
        res.update(
            {
                "seller_id": self.seller_id.id,
            }
        )
        return res

    def _create_invoice(self, move_vals):
        res = super()._create_invoice(move_vals)
        res.write({"seller_id": move_vals["seller_id"]})
        return res

    def _export_for_ui(self, order):
        res = super()._export_for_ui(order)
        seller = False
        if order.seller_id:
            seller = order.seller_id.read(["id","name"])[0]
        res["seller_id"] = seller
        return res
