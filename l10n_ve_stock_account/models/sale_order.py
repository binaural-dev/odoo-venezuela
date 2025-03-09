from odoo import models, fields, api

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
        tracking=True,  # Esto habilita la trazabilidad del campo
        help="Document type for the sale order.",
    )

    @api.model
    def _default_document(self):
        """Get the default value for the document field from the partner's default_document."""
        partner = self.env["res.partner"].browse(
            self._context.get("default_partner_id")
        )
        return partner.default_document if partner else "invoice"

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        """Update the document field when the partner is changed."""
        if self.partner_id:
            self.document = self.partner_id.default_document
        else:
            self.document = "invoice"
