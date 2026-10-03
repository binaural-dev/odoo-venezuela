from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.misc import format_datetime

import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    donation_reason = fields.Char(string="Donation Reason")

    @api.model
    def default_get(self, fields_list):
        """Mark the picking as a donation when it is created from the
        Donations menu.

        The menu passes `donation_menu` instead of `default_is_donation`
        because every `default_*` key of an action context is propagated to
        all the records created from it, including the stock valuation
        journal entries, which must not inherit the donation mark."""
        res = super().default_get(fields_list)
        if self.env.context.get("donation_menu") and "is_donation" in fields_list:
            res["is_donation"] = True
        return res

    def button_validate(self):
        for picking in self:
            if (
                picking.is_donation
                and not picking.sale_id
                and picking.picking_type_code == "outgoing"
                and not picking.partner_id
                and not picking.donation_reason
            ):
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
