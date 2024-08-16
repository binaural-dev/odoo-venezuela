from odoo import fields, models, _
from odoo.exceptions import ValidationError


class SetCommissionOrderToInvoice(models.TransientModel):
    _name = "set.commission.order.to.invoice"
    _description = "Set Commission Order To Invoice"

    company_id = fields.Many2one(
        "res.company", string="Company", required=True, default=lambda self: self.env.company
    )
    sale_order_ids = fields.Many2many("sale.order")
    overwrite_commission = fields.Boolean(default=True)

    def get_orders(self):
        return self.sale_order_ids

    def get_order_lines(self):
        return self.get_orders().order_line

    def get_invoices(self):
        return self.get_orders().invoice_ids

    def remove_commissions(self,orders):
        self.get_order_lines().commission_policy_line_image_ids = False
        self.get_invoices().invoice_line_ids.commission_image_id = False

    def write_documents(self, orders):
        data_write = {
            "commission_invoice_date_field": self.company_id.commission_invoice_date_field,
            "compute_commission_when": self.company_id.compute_commission_when,
            "priority_commission_policy_type": "/".join(
                self.env["commission.policy.type"].search([]).mapped("name")
            ),
        }
        orders.write(data_write)
        orders.assing_commission_policy_line_images_to_order_lines()
        self.get_invoices().write(data_write)
        self.get_invoices()._compute_payment_dates()
        self.get_invoices().calculate_commission()
        return data_write

    def action_confirm(self):
        order_message = []
        invoice_message = []
        invoice_paid_message = []
        orders = self.get_orders()

        available_orders = orders

        if orders._name == "sale.order":
            available_orders = orders.filtered(lambda x: not x.has_invoices_paid)

        if self.overwrite_commission:
            order_message = (
                self.get_order_lines()
                .filtered(lambda x: x.commission_policy_line_image_ids)
                .order_id.mapped("name")
            )
            invoice_message = (
                self.get_invoices()
                .invoice_line_ids.filtered(lambda x: x.commission_image_id)
                .move_id.mapped("name")
            )
            invoice_paid_message = (orders - available_orders).mapped("name")
            self.remove_commissions(orders)

        self.write_documents(orders)

        if sum([len(order_message) + len(invoice_message) + len(invoice_paid_message)]) == 0:
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

        if len(invoice_paid_message) > 0:
            message.append(
                _(
                    """The order(s) already had invoices paid, They have not been processed""",
                )
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Action complete, but..."),
                "type": "warning",
                "message": ",\n".join(message),
                "sticky": True,
            },
        }
