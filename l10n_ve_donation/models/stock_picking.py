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
            if (
                picking.is_donation
                and not picking.sale_id
                and picking.picking_type_code == "outgoing"
            ):
                errors = picking._get_donation_delivery_config_errors()
                if errors:
                    raise UserError("\n".join(errors))
        return super().button_validate()

    def _has_real_time_valuation_moves(self):
        """Whether some non-cancelled move is of a storable product with
        automated (real_time) valuation, i.e. whether the picking generates
        valuation journal entries (the stock valuation skips the products that
        are not storable). The valuation mode is company dependent: it is read
        with the company of the picking, as the stock valuation does
        (`with_company(move.company_id)`), not with the active company of the
        user, which may differ when several companies are enabled."""
        self.ensure_one()
        products = self.move_ids.filtered(
            lambda move: move.state != "cancel"
        ).product_id.with_company(self.company_id)
        return any(
            product.type == "product" and product.valuation == "real_time"
            for product in products
        )

    def _get_donation_delivery_config_errors(self):
        """Return the list of messages describing why the configuration of
        this donation delivery is not coherent (empty if it is).

        The valuation journal entry of the delivery is determined by the
        configuration, not forced by the donation hook: the stock valuation
        takes the debit account from the destination location, which must be
        an `inventory` location. Its incoming valuation account is required
        only when a move has a product with automated (real_time) valuation:
        otherwise the delivery generates no valuation entry. Extension point:
        other modules append their own checks with `super()`."""
        self.ensure_one()
        errors = []
        moves = self.move_ids.filtered(lambda move: move.state != "cancel")
        locations = self.location_dest_id | moves.location_dest_id
        is_real_time = self._has_real_time_valuation_moves()
        for location in locations:
            if location.usage != "inventory":
                # The account of a location that is not a donation destination
                # is not evaluated: the destination itself must be changed.
                errors.append(_(
                    "The destination %(location)s of a donation delivery is not of type "
                    "Inventory Loss. Change the Destination Location of the delivery (or the "
                    "Default Destination Location of its operation type) to an Inventory Loss "
                    "location, e.g. the default destination of the donation operation type.",
                    location=location.display_name,
                ))
            elif is_real_time and not location.valuation_in_account_id:
                errors.append(_(
                    "The destination location %(location)s of a donation delivery has no "
                    "Stock Valuation Account (Incoming). Set it in Inventory > Configuration > "
                    "Locations, in the Accounting Information section of the location.",
                    location=location.display_name,
                ))
        return errors

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
