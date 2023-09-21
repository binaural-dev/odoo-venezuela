import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ["account.move", "filter.partner.mixin"]

    correlative = fields.Char("Control Number", copy=False, help="Sequence control number")
    invoice_reception_date = fields.Date(
        "Reception Date", help="Indicates when the invoice was received by the client/company"
    )
    last_payment_date = fields.Date(
        compute="_compute_last_payment_date",
        store=True
    )
    
    @api.depends("amount_residual")
    def _compute_last_payment_date(self):
        for move in self:
            is_client_invoice = move.move_type == "out_invoice"
            not_amount_residual = move.currency_id.is_zero(move.amount_residual)
            is_invoice_payment_widget = move.invoice_payments_widget
            
            is_valid_invoice = is_client_invoice and not_amount_residual
            is_valid_invoice_payment = is_valid_invoice and is_invoice_payment_widget
            
            reconcilieds = move._get_reconciled_invoices_partials()
            settlement_date = None
            
            if is_valid_invoice_payment:
                settlement_date = self.get_max_payment_date(
                    move.invoice_payments_widget
                )
                
                settlement_date = fields.Date.from_string(settlement_date)
                
                if not settlement_date:
                    if reconcilieds:
                        value = [invoice[0][2].date for invoice in reconcilieds if invoice and not isinstance(invoice[0], int)]
                        if value:
                            settlement_date = max(value)
            else:
                if reconcilieds:
                    value = [invoice[0][2].date for invoice in reconcilieds if invoice and not isinstance(invoice[0], int)]
                    if value: 
                        max_value = max(value)
                        settlement_date = max_value

            move.last_payment_date = settlement_date
            
    @staticmethod
    def get_max_payment_date(payments):
        dates = list()
        
        have_payments = payments.get("content")
        is_valid_process = have_payments and payments
        
        settlement_date = False
        
        if is_valid_process:
            for payment in have_payments:
                account_payment_id = payment.get("account_payment_id", False)
                if account_payment_id:
                    dates.append(payment.get("date", False))
                    
        is_exist_dates = len(dates) > 0            
        if is_exist_dates:
            settlement_date = max(dates)

        return settlement_date


    @api.onchange("invoice_line_ids")
    def _onchange_invoice_line_ids(self):
        """
        Limit the number of products that can be added to the invoice
        """
        if self.invoice_line_ids and self.move_type in ["out_invoice", "out_refund"]:
            max_product_invoice = self.company_id.max_product_invoice
            if len(self.invoice_line_ids) > max_product_invoice:
                raise ValidationError(
                    _("You can not add more than %s products to the invoice." % max_product_invoice)
                )

    @api.depends("filter_partner")
    def _compute_partner_id_domain(self):
        for move in self:
            company_id = move.company_id.id
            extend_domain = [("type", "!=", "private"), ("company_id", "in", (False, company_id))]
            domain = move.get_partner_domain(extend=extend_domain)

            move.update({"partner_id_domain": json.dumps(domain)})

    def _post(self, soft=True):
        res = super()._post(soft)
        for move in res:
            if move.is_valid_to_sequence():
                move.correlative = move.get_sequence(move.journal_id.fiscal)

    @api.model
    def is_valid_to_sequence(self) -> bool:
        """Check if the invoice satisfy the conditions to
        associate a new sequence number.

        Returns
        -------
            True or False whether the invoice already has a
            sequence number or not.
        """

        return self.move_type in ["out_invoice", "out_refund"] and not self.correlative

    @api.model
    def get_sequence(self, is_fiscal=False):
        """Allow the invoice to have both a generic sequence
        number or a specific one given certain conditions.

        Returns
        -------
            The next number from the sequence to be assigned.
        """

        self.ensure_one()
        series_invoicing_enabled = self.company_id.group_sales_invoicing_series
        sequence = self.env["ir.sequence"].sudo()
        correlative = None

        if series_invoicing_enabled and is_fiscal:
            correlative = self.journal_id.series_correlative_sequence_id

            if not correlative:
                raise UserError(_("The sale's series sequence must be in the selected journal."))
            return correlative.next_by_id(correlative.id)

        correlative = sequence.search([("code", "=", "invoice.correlative"),("company_id", "=", self.env.company.id)])
        if not correlative:
            correlative = sequence.create(
                {
                    "name": "Número de control",
                    "code": "invoice.correlative",
                    "padding": 5,
                }
            )
        return correlative.next_by_id(correlative.id)

    def action_post(self,):
        res = super().action_post()
        for move in self:
            if move.journal_id.fiscal and not move.correlative:
                move.correlative = move.get_sequence(move.journal_id.fiscal)
        return res