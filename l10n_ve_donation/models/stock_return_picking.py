from odoo import models, _
from odoo.exceptions import UserError


class StockReturnPicking(models.TransientModel):
    _inherit = "stock.return.picking"

    def _create_return(self):
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
        return super()._create_return()

    def _prepare_picking_default_values_based_on(self, picking):
        """The return of the delivery of a donation sale order must not keep
        the 'Donation' transfer reason that `copy()` would take from it: the
        inventory book counts every move with that reason as a withdrawal,
        whatever its direction, so the return (an incoming move) would be
        counted as an entry and as a withdrawal."""
        vals = super()._prepare_picking_default_values_based_on(picking)
        if picking.is_donation:
            vals["transfer_reason_id"] = False
        return vals
