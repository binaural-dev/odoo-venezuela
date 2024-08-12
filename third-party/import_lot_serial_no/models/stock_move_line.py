# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class stockMoveInherit(models.Model):
    _inherit = "stock.move.line"

    is_serial = fields.Boolean(string="serial or not")

    def _reservation_is_updatable(self, quantity, reserved_quant):
        self.ensure_one()
        if self.is_serial == True:
            if (self.location_id.id == reserved_quant.location_id.id and
                    self.lot_id.id == reserved_quant.lot_id.id and
                    self.package_id.id == reserved_quant.package_id.id and
                    self.owner_id.id == reserved_quant.owner_id.id):
                return True

            return False
        else:
            return super(stockMoveInherit, self)._reservation_is_updatable(quantity=quantity,
                                                                            reserved_quant=reserved_quant)
