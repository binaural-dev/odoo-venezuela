from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    document = fields.Selection(
        [
            ("dispatch_guide", "Dispatch Guide"),
            ("invoice", "Invoice"),
        ],
        string="Document",
        default=lambda self: self._default_document(),
        required=True,
        tracking=True,
        help="Document type for the sale order.",
    )

    is_donation = fields.Boolean(string="Is Donation", default=False, tracking=True)

    is_consignation = fields.Boolean(
        string="Is Consignation",
        compute="_compute_is_consignation",
        store=True,
        help="Indicates if this sale order is a consignation sale.",
    )

    @api.depends("warehouse_id")
    def _compute_is_consignation(self):
        for order in self:
            order.is_consignation = order.warehouse_id and order.warehouse_id.is_consignation_warehouse

    @api.model
    def _default_document(self):
        """Get the default value for the document field from the partner's default_document."""
        partner = self.env["res.partner"].browse(self._context.get("default_partner_id"))
        return partner.default_document if partner else "invoice"

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        """Update the document field when the partner is changed."""
        if self.partner_id:
            self.document = self.partner_id.default_document
        else:
            self.document = "invoice"

    @api.constrains("is_donation", "state")
    def _check_is_donation(self):
        for order in self:
            if (order.state in ["sale", "done"]) and order._origin:
                if order.is_donation != order._origin.is_donation:
                    raise ValidationError(
                        _(
                            "The field 'Is Donation' cannot be modified on a confirmed or completed order."
                        )
                    )
