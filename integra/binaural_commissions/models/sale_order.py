import json
from odoo import api, models, fields, _
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    commission_invoice_date_field = fields.Char(readonly=True, copy=False)
    compute_commission_when = fields.Char(readonly=True, copy=False)
    priority_commission_policy_type = fields.Char(readonly=True, copy=False)
    has_invoices_paid = fields.Boolean(compute="_compute_has_invoices_paid", store=True)

    @api.depends("invoice_ids", "has_invoices_paid", "invoice_ids.commission_payment_state")
    def _compute_has_invoices_paid(self):
        for order in self:
            order.has_invoices_paid = any(
                not invoice._can_recompute_commission() for invoice in order.invoice_ids
            )

    def assing_commission_policy_line_images_to_order_lines(self):
        self.env["commission.policy"].assing_commission_policy_line_images_to_lines(
            self.order_line.filtered(lambda x: not x.display_type)
        )

    def set_company_settings(self):
        self.commission_invoice_date_field = self.company_id.commission_invoice_date_field
        self.compute_commission_when = self.company_id.compute_commission_when
        self.priority_commission_policy_type = "/".join(
            self.env["commission.policy.type"].search([]).mapped("name")
        )

    def _prepare_invoice(self):
        """
        Prepare the dict of values to create the new invoice for a sales order. This method may be
        overridden to implement custom invoice generation (making sure to call super() to establish
        a clean extension chain).
        """
        self.ensure_one()
        res = super()._prepare_invoice()
        res["commission_invoice_date_field"] = self.commission_invoice_date_field
        res["compute_commission_when"] = self.compute_commission_when
        res["priority_commission_policy_type"] = self.priority_commission_policy_type
        return res

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            order.assing_commission_policy_line_images_to_order_lines()
            order.set_company_settings()
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
                default_sale_order_ids=self.ids,
            ),
        }
