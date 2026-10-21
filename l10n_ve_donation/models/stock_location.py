from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class StockLocation(models.Model):
    _inherit = "stock.location"

    is_donation_warehouse = fields.Boolean(
        string="Donation Warehouse",
        compute="_compute_is_donation_warehouse",
        store=True,
    )

    @api.depends("location_id")
    def _compute_is_donation_warehouse(self):
        for record in self:
            warehouse = record.get_warehouse()
            record.is_donation_warehouse = bool(
                warehouse and warehouse.is_donation_warehouse
            )

    def _get_donation_initial_account(self, usage, parent_location):
        """Return the account proposed as the incoming valuation account of a
        location of `usage` under `parent_location`: the donation account of
        the company of the warehouse, if it is the donation warehouse and the
        usage is `inventory`. The warehouse is resolved with `get_warehouse()`,
        not from the stored `is_donation_warehouse` of the parent, which may
        be stale (the view location of a warehouse is created before the
        warehouse itself)."""
        if usage != "inventory" or not parent_location:
            return self.env["account.account"]
        warehouse = parent_location.get_warehouse()
        if not warehouse or not warehouse.is_donation_warehouse:
            return self.env["account.account"]
        return warehouse.company_id.donation_account_id

    @api.onchange("location_id", "usage")
    def _onchange_donation_valuation_in_account(self):
        """Same initial value as `create`, shown in the form when the parent
        or the usage are chosen. It never overwrites an account already set."""
        for location in self:
            if location.valuation_in_account_id:
                continue
            account = location._get_donation_initial_account(location.usage, location.location_id)
            if account:
                location.valuation_in_account_id = account

    @api.model_create_multi
    def create(self, vals_list):
        """Suggest the company donation account as the incoming valuation
        account of a new `inventory` location of the donation warehouse.

        It is only an initial value: an explicit `valuation_in_account_id`
        (even an empty one), or a context default, is respected."""
        default_usage = None
        has_default_account = "default_valuation_in_account_id" in self.env.context
        for vals in vals_list:
            if (
                has_default_account
                or "valuation_in_account_id" in vals
                or not vals.get("location_id")
            ):
                continue
            if "usage" in vals:
                usage = vals["usage"]
            else:
                if default_usage is None:
                    default_usage = self.default_get(["usage"]).get("usage")
                usage = default_usage
            account = self._get_donation_initial_account(usage, self.browse(vals["location_id"]))
            if account:
                vals["valuation_in_account_id"] = account.id
        return super().create(vals_list)

    @api.constrains("usage")
    def _check_donation_delivery_destination(self):
        """The default destination of a donation delivery operation type
        determines the accounts of its journal entries: it must stay an
        `inventory` location."""
        # sudo: the constraint must see the operation types of every company,
        # regardless of the access rights of the user editing the location.
        donation_types = self.env["stock.picking.type"].sudo().search([
            ("is_donation_picking_type", "=", True),
            ("code", "=", "outgoing"),
            ("default_location_dest_id", "in", self.ids),
        ])
        for picking_type in donation_types:
            location = picking_type.default_location_dest_id
            if location.usage != "inventory":
                raise ValidationError(_(
                    "The location %(location)s is the default destination of the donation "
                    "delivery operation type %(picking_type)s, so its Location Type must be "
                    "Inventory Loss.",
                    location=location.display_name,
                    picking_type=picking_type.display_name,
                ))

    def get_warehouse(self):
        """Return the warehouse associated with this stock location, or False if none found."""
        if not self.id:
            return False

        warehouse = self.env["stock.warehouse"].search(
            [
                "|",
                ("lot_stock_id", "=", self.id),
                ("view_location_id", "parent_of", self.id),
            ],
            limit=1,
        )
        return warehouse
