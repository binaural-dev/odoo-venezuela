from odoo import models, _
from odoo.exceptions import UserError


class StockReturnPicking(models.TransientModel):
    _inherit = "stock.return.picking"

    def _create_returns(self):
        """Donations are not returned: neither the deliveries nor the
        receipts created from the Donations menu. Pickings that come from a
        donation sale order are excluded: they follow the regular sale return
        flow. It runs before `super()`, which creates the return picking."""
        for wizard in self:
            picking = wizard.picking_id
            if picking.is_donation and not picking.sale_id:
                raise UserError(_(
                    "The donation %(picking)s cannot be returned: donations "
                    "are not returned.",
                    picking=picking.display_name,
                ))
        return super()._create_returns()
