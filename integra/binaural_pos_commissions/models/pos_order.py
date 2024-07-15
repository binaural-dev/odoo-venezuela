from odoo import fields, models
import logging
_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    commission_invoice_date_field = fields.Char(readonly=True, copy=False)
    compute_commission_when = fields.Char(readonly=True, copy=False)
    priority_commission_policy_type = fields.Char(readonly=True, copy=False)

    def action_pos_order_paid(self):
        res = super().action_pos_order_paid()
        self.assing_commission_policy_line_images_to_order_lines()
        self.set_company_settings()
        return res

    def assing_commission_policy_line_images_to_order_lines(self):
        self.env["commission.policy"].assing_commission_policy_line_images_to_lines(
            self.lines
        )

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
