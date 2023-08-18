from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (
                vals.get("move_type", "") != "in_invoice"
                or vals.get("invoice_origin", False) == False
            ):
                continue

            PurchaseOrderLine = self.env["purchase.order.line"]
            purchase_order = self.env["purchase.order"]
            journal_id = self.env["account.journal"]

            for line in vals.get("invoice_line_ids", []):
                line_data = line[2]
                if purchase_order:
                    continue

                if line_data.get("purchase_line_id", False):
                    order_line = PurchaseOrderLine.browse(line_data.get("purchase_line_id", False))

                    if len(order_line.taxes_id) != 1:
                        raise ValidationError(
                            _("The purchase order line %s has not taxes or have more than one")
                            % order_line.name
                        )

                    purchase_order = order_line.order_id
                    journal_id = purchase_order.journal_invoice_id.id

            if not journal_id:
                raise ValidationError(
                    _("The purchase order %s has not a journal invoice") % purchase_order.name
                )

            vals.update({"journal_id": journal_id})

        return super().create(vals_list)
