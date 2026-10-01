from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.misc import format_datetime

import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    donation_reason = fields.Char(string="Donation Reason")

    is_donation_delivery = fields.Boolean(
        compute="_compute_is_donation_delivery",
        help="Light computed field used to drive view visibility -- "
        "`invisible` attributes in the arch cannot call a method directly.",
    )

    @api.depends("picking_type_id.is_donation_picking_type", "picking_type_id.code")
    def _compute_is_donation_delivery(self):
        for picking in self:
            picking.is_donation_delivery = picking._is_donation_delivery()

    def _is_donation_delivery(self):
        """True only for the OUTGOING direction -- `is_donation_picking_type`
        is now a shared flag (also set by higea_donation on its incoming
        receipt type), so this module must check `code` explicitly to stay
        scoped to its own direction."""
        self.ensure_one()
        return bool(self.picking_type_id.is_donation_picking_type) and self.picking_type_id.code == "outgoing"

    def button_validate(self):
        for picking in self:
            if picking._is_donation_delivery() and not picking.partner_id and not picking.donation_reason:
                raise UserError(_(
                    "You must set the recipient (Contact) or the donation reason "
                    "to validate a donation delivery."
                ))
        return super().button_validate()

    def _get_donation_product_lines(self):
        """Per-line detail (code, description, qty, uom, lot, expiration,
        cost) -- via stock_valuation_layer_ids, not product_id.standard_price,
        so reprinting always gives the same number.

        `expiration_date` is resolved here (not in the shared report
        sub-template): `stock.lot.expiration_date` only exists when
        `product_expiry` is installed, an optional dependency this module
        does not require. It is formatted with `format_datetime` (user's
        language/timezone), with `dt_format=False` so it uses the user's
        language date/time format -- same style `t-field` would use
        elsewhere in this same document -- rather than left as a raw
        datetime; the shared template only does `t-out` on the
        already-resolved value, not `t-field`."""
        self.ensure_one()
        data = []
        for line in self.move_line_ids:
            layers = line.move_id.stock_valuation_layer_ids
            total_qty = sum(layers.mapped("quantity"))
            total_value = sum(layers.mapped("value"))
            unit_cost = abs(total_value / total_qty) if total_qty else 0.0
            expiration_date = (
                format_datetime(self.env, line.lot_id.expiration_date, dt_format=False)
                if line.lot_id and "expiration_date" in line.lot_id._fields and line.lot_id.expiration_date
                else False
            )
            data.append({
                "line": line,
                "unit_cost": unit_cost,
                "total_value": unit_cost * line.quantity,
                "expiration_date": expiration_date,
            })
        return data

    def _get_donation_grand_total(self):
        self.ensure_one()
        return sum(row["total_value"] for row in self._get_donation_product_lines())

    def print_donation_certificate(self):
        self.ensure_one()
        return self.env.ref("l10n_ve_donation.action_donation_delivery_certificate").report_action(self)
