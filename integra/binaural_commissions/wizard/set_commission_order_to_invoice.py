from odoo import fields, models, _


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
        for sale_order in self.sale_order_ids:
            sale_order.set_company_settings()
            for line in sale_order.order_line:
                if not self.overwrite_commission:
                    continue
                if not line.commission_policy_line_image_ids:
                    continue
                if line.order_id.name not in order_message:
                    order_message.append(line.order_id.name)
                line.commission_policy_line_image_ids = False
            sale_order.assing_commission_policy_line_images_to_order_lines()
            for invoice in sale_order.invoice_ids:
                invoice.write(
                    {
                        "commission_invoice_date_field": sale_order.commission_invoice_date_field,
                        "compute_commission_when": sale_order.compute_commission_when,
                    }
                )
                for line in invoice.invoice_line_ids:
                    if not self.overwrite_commission:
                        continue
                    if not line.commission_image_id:
                        continue
                    if invoice.name not in invoice_message:
                        invoice_message.append(invoice.name)
                    line.commission_image_id = False

                invoice.calculate_commission()

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
