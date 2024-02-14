from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)

LABEL = {
    "invoice_date": _("Fecha de Factura"),
    "invoice_reception_date": _("Fecha de Recepción"),
    "invoice_is_fully_paid": _("Factura pagada completamente"),
    "invoice_first_payment": _("Primera fecha de pago"),
}


class AccountMove(models.Model):
    _inherit = "account.move"

    commission_invoice = fields.Many2one(
        "account.move",
        string="Invoice Commission",
    )
    origin_commission_invoice = fields.One2many("account.move", "commission_invoice")
    collection_days = fields.Integer(compute="_compute_collection_days")
    total_commission = fields.Float(compute="_compute_total_commission_of_invoice", store=True)

    # discount_invoice = fields.Many2many(
    #     "account.move", "reversal_move_id", "move_id", compute="_compute_discount_invoice"
    # )

    commission_payment_state = fields.Selection(
        [("not_paid", "not paid"), ("process", "in process"), ("paid", "paid")],
        compute="_compute_paid_seller",
        store=True,
        help="Payment State (Commission Invoice)",
    )

    commission_discount = fields.Float(
        # compute="_compute_discount_invoice",
        store=True,
        help="Discount of corrective payments",
    )

    commission_invoice_date_field = fields.Char(readonly=True, copy=False)
    compute_commission_when = fields.Char(readonly=True, copy=False)
    label_commission_invoice_date_field = fields.Char(compute="_compute_field_settings")
    label_commission_when = fields.Char(compute="_compute_field_settings")
    is_commission_invoice = fields.Boolean(readonly=True, copy=False)

    def action_post(self):
        for record in self:
            if record.is_commission_invoice and not record.invoice_date:
                record.invoice_date = fields.Date.context_today(self)
        return super().action_post()

    @api.depends("commission_invoice_date_field", "compute_commission_when")
    def _compute_field_settings(self):
        for record in self:
            record.label_commission_invoice_date_field = LABEL.get(
                record.commission_invoice_date_field, ""
            )
            record.label_commission_when = LABEL.get(record.compute_commission_when, "")

    def button_cancel(self):
        for record in self:
            if record.commission_invoice:
                record.commission_invoice.button_cancel()

            if record.origin_commission_invoice:
                for invoice in record.origin_commission_invoice:
                    invoice.commission_invoice = False
        return super().button_cancel()

    @api.depends("commission_invoice", "commission_invoice.payment_state", "total_commission")
    def _compute_paid_seller(self):
        for record in self:
            if not record.commission_invoice:
                record.commission_payment_state = "not_paid"
                continue
            if record.commission_invoice.payment_state in ["paid", "in_payment"]:
                record.commission_payment_state = "paid"
                continue
            record.commission_payment_state = "process"

    def show_invoice_resume(self):
        view = self.env.ref("binaural_commissions.invoice_commission_summary_wizard_form_view")

        invoice_lines = self.invoice_line_ids.filtered(lambda x: x.commission_image_id != False)

        return {
            "name": _("Resumen de Factura"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "invoice.commission.summary.wizard",
            "views": [(view.id, "form")],
            "view_id": view.id,
            "target": "new",
            "flags": {"mode": "readonly"},
            "context": dict(
                self.env.context,
                default_name=self.name,
                default_invoice_line_ids=invoice_lines.ids,
            ),
        }

    def generate_seller_in_invoices(self):
        for record in self:
            if record.state != "posted":
                raise ValidationError(_("Only posted invoices can be processed."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Generate Commission"),
            "res_model": "generate.commission.from.invoice",
            "view_mode": "form",
            "view_id": self.env.ref("binaural_commissions.generate_commission_from_invoice").id,
            "target": "new",
            "context": {
                "default_invoice_ids": self.ids,
                "default_seller_id": self.seller_id[0].user_partner_id.id,
            },
        }

    @api.depends(
        "amount_residual",
        "collection_days",
        "invoice_reception_date",
        "invoice_date",
        "first_payment_date",
        "last_payment_date",
    )
    def _compute_total_commission_of_invoice(self):
        for record in self:
            if not record._can_recompute_commission():
                record.total_commission = record.total_commission
                continue

            if not record.is_valid_to_compute_commission():
                record.total_commission = 0
                for line in record.invoice_line_ids:
                    line.commission_image_id = False
                    line.commission_amount = 0
                continue

            total = False
            for line in record.invoice_line_ids:
                if line.sale_line_ids.commission_policy_line_image_ids:
                    commission_id = line.sale_line_ids.get_commission_policy_line_image(
                        record.collection_days
                    )

                    if commission_id and len(commission_id) > 1:
                        raise ValidationError(
                            _(
                                "The commission policy has more than one record with the same date range."
                            )
                        )
                    line.commission_image_id = commission_id
                    line.commission_amount = line.price_subtotal * (
                        line.commission_image_id.commission / 100
                    )
                    total += line.commission_amount
            record.total_commission = total

    def _can_recompute_commission(self):
        """Check if the invoice can be recomputed."""
        if self.commission_payment_state not in ["not_paid", False]:
            return False
        return True

    def is_valid_to_compute_commission(self):
        """Check if the invoice is valid to compute commission."""
        self.ensure_one()
        if (
            self.compute_commission_when == "invoice_is_fully_paid"
            and not self.currency_id.is_zero(self.amount_residual)
        ):
            return False
        if self.compute_commission_when == "invoice_first_payment" and not self.first_payment_date:
            return False
        if self.compute_commission_when == "invoice_is_fully_paid" and not self.last_payment_date:
            return False
        if self.collection_days == 0 and (
            self._get_commission_date_from()
            and self._get_commission_date_to()
            and self._get_commission_date_from() != self._get_commission_date_to()
        ):
            return False
        if self.state != "posted":
            return False
        return True

    @api.depends("invoice_date_due", "invoice_date")
    def _compute_collection_days(self):
        for record in self:
            days = 0
            date_from = record._get_commission_date_from()
            date_to = record._get_commission_date_to()
            if date_from and date_to:
                days = (date_to - date_from).days
            record.collection_days = days

    def _get_commission_date_from(self):
        self.ensure_one()
        invoice_date_field = self.commission_invoice_date_field
        if invoice_date_field == "invoice_reception_date":
            return self.invoice_reception_date
        if invoice_date_field == "invoice_date":
            return self.invoice_date
        return False

    def _get_commission_date_to(self):
        self.ensure_one()
        payment_type = self.compute_commission_when
        if payment_type == "invoice_is_fully_paid":
            return self.last_payment_date
        if payment_type == "invoice_first_payment":
            return self.first_payment_date

        return False
