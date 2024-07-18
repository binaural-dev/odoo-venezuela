from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero, float_round

import json
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

    origin_commission_invoice = fields.One2many("account.move", "commission_invoice")
    collection_days = fields.Integer(compute="_compute_collection_days", store=True, copy=False)
    total_commission = fields.Float(
        compute="_compute_total_commission_of_invoice", store=True, copy=False
    )
    discount_invoice_ids = fields.Many2many(
        "account.move", compute="_compute_discount_invoice", compute_sudo=True
    )
    commission_invoice_date_field = fields.Char(readonly=True, copy=False)
    compute_commission_when = fields.Char(readonly=True, copy=False)
    priority_commission_policy_type = fields.Char(readonly=True, copy=False)
    label_commission_invoice_date_field = fields.Char(compute="_compute_field_settings")
    label_commission_when = fields.Char(compute="_compute_field_settings")
    is_commission_invoice = fields.Boolean(readonly=True, copy=False)
    commission_invoice = fields.Many2one(
        "account.move",
        string="Invoice Commission",
    )
    commission_payment_state = fields.Selection(
        [("not_paid", "not paid"), ("process", "in process"), ("paid", "paid")],
        compute="_compute_paid_seller",
        store=True,
        copy=False,
        help="Payment State (Commission Invoice)",
    )
    commission_discount = fields.Float(
        compute="_compute_discount_invoice",
        compute_sudo=True,
        store=True,
        copy=False,
        help="Discount of corrective payments",
    )

    # ---------------------
    # ~ Odoo methods
    # ---------------------

    def action_post(self):
        """
        Set the invoice date when the invoice is a commission invoice and click on button Confirm.
        """
        for record in self:
            if record.is_commission_invoice and not record.invoice_date:
                record.invoice_date = fields.Date.context_today(self)
        return super().action_post()

    def button_cancel(self):
        """
        This function has effect on the commission invoice and the origin commission invoice.

        if click on button Cancel:
            - Set the commission_invoice field to False.
            - Set the commission_invoice field to False in the origin commission invoice.
        """
        for record in self:
            if record.commission_invoice:
                record.commission_invoice.button_cancel()

            if record.origin_commission_invoice:
                for invoice in record.origin_commission_invoice:
                    invoice.commission_invoice = False
        return super().button_cancel()

    # ---------------------
    # ~ Commission compute
    # ---------------------

    @api.depends("commission_invoice_date_field", "compute_commission_when")
    def _compute_field_settings(self):
        for record in self:
            record.label_commission_invoice_date_field = LABEL.get(
                record.commission_invoice_date_field, ""
            )
            record.label_commission_when = LABEL.get(record.compute_commission_when, "")

    @api.depends("commission_invoice", "commission_invoice.payment_state", "total_commission")
    def _compute_paid_seller(self):
        """Compute the payment state of the commission invoice."""
        for record in self:
            if not record.commission_invoice:
                record.commission_payment_state = "not_paid"
                continue
            if record.commission_invoice.payment_state in ["paid", "in_payment"]:
                record.commission_payment_state = "paid"
                continue
            record.commission_payment_state = "process"

    def get_reversed_entry(self):
        return self.reversed_entry_id

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
            if record.move_type == "out_refund":
                out_invoice = record.get_reversed_entry()

                for line in record.invoice_line_ids:
                    out_invoice_line = out_invoice.invoice_line_ids.filtered(
                        lambda x: x.product_id == line.product_id
                    )
                    if not out_invoice_line.commission_image_id:
                        continue
                    line.commission_image_id = out_invoice_line.commission_image_id

                record.total_commission = total
                return

            for line in record.invoice_line_ids:
                commission_id = line.get_commission(record.collection_days)
                if not commission_id:
                    continue

                if len(commission_id) > 1:
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

    @api.depends("invoice_date_due", "invoice_date")
    def _compute_collection_days(self):
        for record in self:
            days = 0
            date_from = record._get_commission_date_from()
            date_to = record._get_commission_date_to()
            if date_from and date_to:
                days = (date_to - date_from).days
            record.collection_days = days

    @api.depends("amount_residual")
    def _compute_discount_invoice(self):
        for record in self:
            commission_discount = 0
            discount_invoice_ids = self.env["account.move"]

            if (
                not record.currency_id.is_zero(record.amount_residual)
                or record.move_type != "out_invoice"
            ):
                record.discount_invoice_ids = False
                record.commission_discount = False
                continue

            if not record.invoice_payments_widget:
                record.discount_invoice_ids = False
                record.commission_discount = False
                continue

            discount_invoice_ids, commission_discount = record.get_discount_invoice(
                record.invoice_payments_widget
            )
            record.discount_invoice_ids = discount_invoice_ids
            record.commission_discount = abs(commission_discount) * -1

    # ---------------------
    # ~ Actions
    # ---------------------

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
        self.is_valid_to_generate_commission()
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

    # ---------------------
    # ~ onchange
    # ---------------------

    @api.onchange("invoice_reception_date")
    def _onchange_invoice_reception_date(self):
        if self._origin.invoice_reception_date and not self.invoice_reception_date:
            raise ValidationError(_("The reception date cannot be empty after the set date."))

    # ---------------------
    # ~ Methods
    # ---------------------

    def calculate_commission(self):
        for invoice in self:
            invoice._compute_field_settings()
            invoice._compute_collection_days()
            invoice._compute_discount_invoice()
            invoice._compute_total_commission_of_invoice()

    def is_valid_to_generate_commission(self):
        invoices_not_paid = []
        invoices_with_commission_invoice = []

        for record in self:
            if record.state != "posted":
                raise ValidationError(_("Only posted invoices can be processed."))

            if record.commission_invoice:
                invoices_with_commission_invoice.append(record.name)

            if record.amount_residual > 0:
                invoices_not_paid.append(record.name)

        if len(invoices_with_commission_invoice) > 0:
            raise ValidationError(
                _(
                    "The invoices %s already has a commission invoice in process",
                    ", ".join(invoices_with_commission_invoice),
                )
            )

        if len(invoices_not_paid) > 0:
            raise ValidationError(
                _("The invoice(s) %s have an amount pending to pay.", ", ".join(invoices_not_paid))
            )

    def _can_recompute_commission(self):
        """Check if the invoice can be recomputed."""
        if self.commission_payment_state not in ["not_paid", False]:
            return False
        return True

    def is_valid_to_compute_commission(self):
        """Check if the invoice is valid to compute commission."""
        self.ensure_one()
        if self.move_type not in ["out_invoice", "out_refund"]:
            return False
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

    def get_discount_invoice(self, invoice_payments_widget):
        self.ensure_one()
        invoice_ids = self.env["account.move"]
        total_commission = 0

        if not invoice_payments_widget.get("content", False):
            return invoice_ids, total_commission

        for payment in invoice_payments_widget["content"]:
            account_payment_id = payment.get("account_payment_id", False)
            if account_payment_id:
                continue

            invoice = payment.get("move_id", False)
            if not invoice:
                continue

            out_refund_id = self.browse(int(invoice))
            if not out_refund_id or not out_refund_id.get_reversed_entry():
                continue

            amount_total = 0
            out_invoice_id = out_refund_id.get_reversed_entry()

            for out_refund_line in out_refund_id.invoice_line_ids:
                if out_refund_line.product_id.id in out_invoice_id.invoice_line_ids.product_id.ids:
                    out_invoice_line = out_invoice_id.invoice_line_ids.filtered(
                        lambda inv: inv.product_id.id == out_refund_line.product_id.id
                    )
                    amount_total += self.calculate_commission_product(
                        out_refund_line.price_subtotal,
                        out_invoice_line.commission_image_id.commission,
                        out_refund_id.currency_id.decimal_places,
                    )
                else:
                    subtotal = sum(
                        out_invoice_id.invoice_line_ids.filtered(
                            lambda line: line.commission_image_id
                        ).mapped("price_subtotal")
                    )
                    if not subtotal:
                        continue

                    percentaje = float_round(
                        (out_refund_line.price_subtotal * 100) / subtotal,
                        self.currency_id.decimal_places,
                    )

                    discount = out_invoice_id.total_commission * percentaje / 100
                    amount_total += discount

            percentaje = float_round(
                (payment.get("amount", 0) * 100) / out_refund_id.amount_total,
                precision_digits=self.currency_id.decimal_places,
            )
            total_commission += float_round(
                amount_total * (percentaje / 100), precision_digits=self.currency_id.decimal_places
            )
            invoice_ids |= out_refund_id

        return invoice_ids, total_commission

    @api.model
    def calculate_commission_product(self, amount_untaxed, commission, currency):
        currency_id = self.env["res.currency"].browse(currency)
        total_commission = 0
        if (
            not float_is_zero(commission, precision_digits=currency_id.decimal_places)
            and amount_untaxed
        ):
            total = (commission / 100) * amount_untaxed
            total_commission = float_round(total, precision_digits=currency_id.decimal_places)

        return total_commission

    def set_reversed(self):
        for record in self:
            if record.ref:
                record.reversed_entry_id = record.env["account.move"].search(
                    [("name", "=", record.ref)]
                )
