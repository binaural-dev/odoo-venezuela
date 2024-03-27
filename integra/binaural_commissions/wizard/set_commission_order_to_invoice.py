from odoo import fields, models, _
from odoo.exceptions import ValidationError


class SetCommissionOrderToInvoice(models.Model):
    _name = "set.commission.order.to.invoice"
    _description = "Set Commission Order To Invoice"

    company_id = fields.Many2one(
        "res.company", string="Company", required=True, default=lambda self: self.env.company
    )
    sale_order_ids = fields.Many2many("sale.order")
    overwrite_commission = fields.Boolean(default=True)

    def action_confirm(self):
        order_message = []
        invoice_message = []

        if self.overwrite_commission:
            order_message = self.sale_order_ids.order_line.filtered(
                lambda x: x.commission_policy_line_image_ids
            ).order_id.mapped("name")
            invoice_message = self.sale_order_ids.invoice_ids.invoice_line_ids.filtered(
                lambda x: x.commission_image_id
            ).move_id.mapped("name")

            self.sale_order_ids.order_line.commission_policy_line_image_ids = False
            self.sale_order_ids.invoice_ids.invoice_line_ids.commission_image_id = False

        data_write = {
            "commission_invoice_date_field": self.company_id.commission_invoice_date_field,
            "compute_commission_when": self.company_id.compute_commission_when,
            "priority_commission_policy_type": "/".join(self.env["commission.policy.type"].search([]).mapped("name"))
        }
        
        if self.sale_order_ids.filtered(lambda x: x.state not in ["done","sale"]):
            raise ValidationError(_("Only orders in state 'Sale' or 'Done' can be processed"))

        self.sale_order_ids.write(data_write)
        self.sale_order_ids.assing_commission_policy_line_images_to_order_lines()

        self.sale_order_ids.invoice_ids.write(data_write)
        self.sale_order_ids.invoice_ids.calculate_commission()

        if len(order_message) == 0 and len(invoice_message) == 0:
            return True

        message = []

        if len(order_message) > 0:
            message.append(
                _(
                    """The order(s) %s already had commissions assigned, 
                    they have been deleted and it has been generated again
                    """,
                    ", ".join(order_message),
                )
            )

        if len(invoice_message) > 0:
            message.append(
                _(
                    """The invoice(s) %s already had commissions assigned, 
                    they have been deleted and it has been generated again
                    """,
                    ", ".join(invoice_message),
                )
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Action complete, but..."),
                "type": "warning",
                "message": "\n".join(message),
                "sticky": True,
            },
        }
