from odoo import _, api, fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    restrict_add_exceeding_quantity = fields.Boolean(default=True)
    supervisor_required_to_edit = fields.Boolean(default=False)
    supervisor_required_for_incomplete_qty = fields.Boolean(default=False)

    def _get_barcode_config(self):
        """
        This function is used to add new fields in the barcode configuration
        """
        res = super()._get_barcode_config()
        res["restrict_add_exceeding_quantity"] = self.restrict_add_exceeding_quantity
        res["supervisor_required_to_edit"] = self.supervisor_required_to_edit
        res["supervisor_required_for_incomplete_qty"] = self.supervisor_required_for_incomplete_qty
        return res

    def _get_fields_stock_barcode(self):
        res = super()._get_fields_stock_barcode()
        res.append("type_steps")
        return res
