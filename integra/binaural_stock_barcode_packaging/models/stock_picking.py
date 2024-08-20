from odoo import models, _


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def open_packaging_qty(self):
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": "stock.picking",
            "view_mode": "form",
            "target": "new",
            "res_id": self.id,
            "views": [
                [
                    self.env.ref("binaural_stock_barcode_packaging.view_picking_form_packaging").id,
                    "form",
                ]
            ],
        }

    def print_packaging_from_barcode(self):
        if self.package_qty > 0:
            return {
                "valid": True,
                "action": ["binaural_stock.action_packaging_picking", {"active_ids": [self.id]}],
            }
        return {"valid": False, "action": {"message": _("The package qty is 0"), "type": "danger"}}
