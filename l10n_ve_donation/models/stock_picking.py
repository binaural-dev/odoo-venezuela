from odoo import models, fields, api

import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    is_donation = fields.Boolean(
        string="Is Donation",
        compute="_compute_is_donation",
        readonly=False,
        tracking=True,
        store=True,
        help="Marks the picking as a donation. It is set by the Donations "
        "menu or when the picking is created from a donation sale order.",
    )
    donation_reason = fields.Char(string="Donation Reason")

    @api.depends("sale_id.is_donation")
    def _compute_is_donation(self):
        """Pickings of a donation sale order are donations. Pickings without
        a sale order keep the value they already have (the Donations menu
        sets it through `default_get`)."""
        for picking in self:
            if picking.sale_id:
                picking.is_donation = picking.sale_id.is_donation
            else:
                picking.is_donation = picking.is_donation

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

    @api.depends("is_donation", "is_dispatch_guide", "operation_code", "location_dest_id")
    def _compute_allowed_reason_ids(self):
        """A donation delivery uses the 'Donation' transfer reason (the
        inventory book classifies the movement by its code). The reason is
        added to the allowed ones, not substituted: the base computation
        rewrites any reason that is not in the allowed list."""
        super()._compute_allowed_reason_ids()
        donation_reason = self._get_donation_transfer_reason()
        if not donation_reason:
            return
        for picking in self:
            if not picking._is_donation_delivery_picking():
                continue
            picking.allowed_reason_ids |= donation_reason
            if picking.transfer_reason_id != donation_reason:
                picking.transfer_reason_id = donation_reason

    @api.model
    def _get_donation_transfer_reason(self):
        return self.env.ref(
            "l10n_ve_stock_account.transfer_reason_donation", raise_if_not_found=False
        )

    def _is_donation_delivery_picking(self):
        """Outgoing donation (with or without sale order): the 'Donation'
        reason does not apply to receipts, the inventory book would count
        them as withdrawals."""
        self.ensure_one()
        return bool(self.is_donation and self.operation_code == "outgoing")

    def _assign_donation_transfer_reason(self):
        """The reason is also assigned after `create`/`write`: when the
        reason arrives in the values (the base gives each new picking the
        default reason of its operation type) the computation of the
        allowed reasons cannot overwrite it."""
        reason = self._get_donation_transfer_reason()
        if not reason:
            return
        for picking in self:
            if picking._is_donation_delivery_picking() and picking.transfer_reason_id != reason:
                picking.transfer_reason_id = reason
            if picking._is_donation_delivery_picking() and reason not in picking.allowed_reason_ids:
                picking.allowed_reason_ids |= reason

    @api.model_create_multi
    def create(self, vals_list):
        pickings = super().create(vals_list)
        pickings._assign_donation_transfer_reason()
        return pickings

    def write(self, vals):
        res = super().write(vals)
        if {"is_donation", "picking_type_id", "sale_id"} & set(vals):
            self._assign_donation_transfer_reason()
        return res
