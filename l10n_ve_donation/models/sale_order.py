from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_donation = fields.Boolean(string="Is Donation", default=False, tracking=True)

    @api.onchange("is_donation")
    def _onchange_is_donation(self):
        if self.is_donation:
            self.partner_id = self.company_id.partner_id
            self.document = "invoice"

    @api.onchange("partner_id")
    def _onchange_partner_id_donation(self):
        """Update the document field when the partner is changed."""
        company_id = self.env.company or self.company_id
        if self.is_donation:
            if self.partner_id != company_id.partner_id:
                raise ValidationError(
                    _(
                        "The Contact/Customer cannot be changed when it is a donation."
                    )
                )

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

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        invoice_vals["is_donation"] = self.is_donation
        return invoice_vals
