from odoo import models, fields, api, _
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = "stock.picking"

    is_donation = fields.Boolean(
        string="Is Donation",
        compute="_compute_is_donation",
        readonly=False,
        tracking=True,
        store=True,
    )

    @api.depends("sale_id.is_donation")
    def _compute_is_donation(self):
        for picking in self:
            picking.is_donation = picking.sale_id.is_donation if picking.sale_id else False

    @api.onchange("is_donation")
    def _onchange_is_donation(self):
        if self.is_donation:
            contact_id = self.env.company.partner_id
            self.partner_id = contact_id
            self.is_dispatch_guide = False

    @api.onchange("partner_id")
    def _onchange_partner_id_donation(self):
        if self.is_donation:
            if self.partner_id != self.env.company.partner_id:
                raise UserError(_("The partner must be the company itself for a donation"))

    @api.depends("is_donation")
    def _compute_picking_type_domain(self):
        super()._compute_picking_type_domain()
        for picking in self:
            if picking.is_donation:
                picking.picking_type_domain = "[('is_donation_picking_type', '=', True)]"

    def create_invoice(self):
        invoice = super().create_invoice()
        if invoice and self.is_donation:
            invoice.write({"is_donation": True})
        return invoice

    @api.depends("is_donation", "is_dispatch_guide", "operation_code", "location_dest_id")
    def _compute_allowed_reason_ids(self):
        super()._compute_allowed_reason_ids()
        for picking in self:
            if picking.is_donation:
                reasons = self.env["transfer.reason"].search([
                    ("id", "in", picking.allowed_reason_ids.ids)
                ])
                self_consumption_reason = self.env.ref("l10n_ve_stock_account.transfer_reason_self_consumption", raise_if_not_found=False)
                if self_consumption_reason:
                    picking.allowed_reason_ids = [(4, self_consumption_reason.id)]
                    picking.transfer_reason_id = self_consumption_reason.id
