from odoo import fields, models, _


class PosOrder(models.Model):
    _inherit = "pos.order"

    commission_invoice_date_field = fields.Char(readonly=True, copy=False)
    compute_commission_when = fields.Char(readonly=True, copy=False)
    priority_commission_policy_type = fields.Char(readonly=True, copy=False)
    commission_payment_state = fields.Selection(related="account_move.commission_payment_state")

    def action_pos_order_paid(self):
        res = super().action_pos_order_paid()
        self.assing_commission_policy_line_images_to_order_lines()
        self.set_company_settings()
        return res

    def assing_commission_policy_line_images_to_order_lines(self):
        lines = self.lines
        if self.company_id.use_image_from_sale_order:

            lines = self.lines.filtered(
                lambda line: not line.sale_order_line_id.commission_policy_line_image_ids
            )
            lines_from_sale_order = self.lines - lines
            for line in lines_from_sale_order:
                line.commission_policy_line_image_ids = (
                    line.sale_order_line_id.commission_policy_line_image_ids
                )

        for line in lines:
            if line.refunded_orderline_id:
                line.commission_policy_line_image_ids = (
                    line.refunded_orderline_id.commission_policy_line_image_ids
                )
                lines -= line

        self.env["commission.policy"].assing_commission_policy_line_images_to_lines(lines)

    def set_company_settings(self):
        self.commission_invoice_date_field = self.company_id.commission_invoice_date_field
        self.compute_commission_when = self.company_id.compute_commission_when
        self.priority_commission_policy_type = "/".join(
            self.env["commission.policy.type"].search([]).mapped("name")
        )

    def _prepare_invoice_vals(self):
        res = super()._prepare_invoice_vals()
        res["commission_invoice_date_field"] = self.commission_invoice_date_field
        res["compute_commission_when"] = self.compute_commission_when
        res["priority_commission_policy_type"] = self.priority_commission_policy_type
        return res

    def set_commission_from_sale(self):
        view = self.env.ref("binaural_commissions.set_commission_order_to_invoice_form")
        return {
            "name": _("Set Commission Order to Invoice"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "set.commission.order.to.invoice",
            "views": [(view.id, "form")],
            "view_id": view.id,
            "target": "new",
            "flags": {"mode": "readonly"},
            "context": dict(
                self.env.context,
                default_pos_order_ids=self.ids,
            ),
        }

    def _get_fields_for_order_line(self):
        """This function is here to be overriden"""
        res = super()._get_fields_for_order_line(self)
        res.append("pricelist_item_id")
        return res

    def _export_for_ui(self, order):
        res = super()._export_for_ui(order)
        res["commission_payment_state"] = order.commission_payment_state
        return res
