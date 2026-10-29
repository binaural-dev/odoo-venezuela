from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_donation = fields.Boolean(string="Is Donation", default=False, tracking=True)

    @api.onchange("is_donation")
    def _onchange_is_donation(self):
        if self.is_donation:
            self.document = "invoice"
            warehouse_id = self.env["stock.warehouse"].search(
                [
                    ("is_donation_warehouse", "=", True),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=1,
            )
            if not warehouse_id:
                raise ValidationError(
                    _(
                        "No donation warehouse found. \nIf you wish to configure one, please go to Inventory > Configuration > Warehouses \nand select a warehouse as 'Donation Warehouse'."
                    )
                )
            self.warehouse_id = warehouse_id
        else:
            if getattr(self, 'is_consignation', False):
                return
            warehouse_id = self.env["stock.warehouse"].search(
                [
                    ("is_donation_warehouse", "=", False),
                    ("is_consignation_warehouse", "=", False),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=1,
            )
            if warehouse_id:
                self.warehouse_id = warehouse_id

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        invoice_vals["is_donation"] = self.is_donation
        return invoice_vals

    def write(self, vals):
        if "is_donation" in vals:
            for order in self:
                if order.state in ["sale", "done"] and order.is_donation != vals["is_donation"]:
                    raise ValidationError(
                        _(
                            "The field 'Is Donation' cannot be modified on a confirmed or completed order."
                        )
                    )
        return super().write(vals)
