from datetime import datetime, date, timedelta
import json
import logging
import calendar
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import format_date

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = "account.move"

    correlative = fields.Char("Control Number", copy=False, help="Sequence control number")
    declaration_unique_of_customs = fields.Char('Declaration unique of customs', copy=False)
    is_purchase_international = fields.Boolean(related='journal_id.is_purchase_international', string='Is International Purchase')

    invoice_date = fields.Date(
        string="Invoice Date",
        default=fields.Date.today,
        help="Date of the invoice. Defaults to today when creating a new invoice."
    )
    
    tax_base_for_international_purchase = fields.Float(string='Tax Base for International Purchase', help='Tax base for international purchase to show in purchase book')
    
    tax_amount_for_international_purchase = fields.Float(string='Tax Amount for International Purchase', help='Tax amount for international purchase to show in purchase book')
    
    invoice_reception_date = fields.Date(
        "Reception Date",
        help="Indicates when the invoice was received by the client/company",
        tracking=True,
    )
    last_payment_date = fields.Date(compute="_compute_payment_dates", store=True)
    first_payment_date = fields.Date(compute="_compute_payment_dates", store=True)
    is_contingency = fields.Boolean(related="journal_id.is_contingency")

    next_installment_date = fields.Date(compute="_compute_next_installment_date")

    display_date_warning = fields.Boolean(
        compute="_compute_display_date_warning")

    is_debit_journal = fields.Boolean(
        compute="_compute_is_debit_journal",
        store=True
    )

    entry_in_period = fields.Boolean(
        compute="_compute_entry_in_period",
    )


    @api.constrains('invoice_date_display', 'date')
    def _check_invoice_date_display_purchases(self):
        for move in self:
            _logger.warning(f"Checking invoice_date_display constraint for move {move.id} with move_type {move.move_type} and company setting block_invoice_display_date_upper_than_date {move.company_id.block_invoice_display_date_upper_than_date}")
            if move.is_purchase_document(include_receipts=True) and move.company_id.block_invoice_display_date_upper_than_date:
                if move.invoice_date_display and move.date and move.invoice_date_display > move.date:
                    raise ValidationError(_("The invoice date cannot be greater than the accounting date."))
    import_file_number_purchase_international = fields.Char(string="Import File Number Purchase International")

    @api.depends("invoice_date", "state")
    def _compute_entry_in_period(self):
        """Computing that allows determining whether an account move (invoice, debit/credit note or receipt) is within the current fiscal period."""
        today = date.today()
        taxpayer_type = self.env.company.taxpayer_type
        period_limit = self._get_period_limit(today, taxpayer_type)

        for move in self:
            move.entry_in_period = False

            if move.state == "cancel":
                continue

            if move.move_type in ("in_invoice", "in_refund", "in_receipt"):
                move.entry_in_period = True
                continue

            if move.move_type in ("out_invoice", "out_refund"):
                if not move.invoice_date:
                    continue

                if (move.invoice_date.year, move.invoice_date.month) == (period_limit.year, period_limit.month) and move.invoice_date <= period_limit:
                    if taxpayer_type == "special" and move.invoice_date.day < 15 < period_limit.day:
                        move.entry_in_period = False
                    else:
                        move.entry_in_period = True

    def _get_period_limit(self, today, taxpayer_type):
        """Returns the tax period deadline according to the taxpayer type."""
        if taxpayer_type == "special":
            if today.day < 15:
                return today.replace(day=15)
        last_day = calendar.monthrange(today.year, today.month)[1]
        return date(today.year, today.month, last_day)

    @api.constrains("invoice_line_ids")
    def _check_price_in_zero(self):
        from_pos = self.env.context.get('from_pos', False)
        for line in self.filtered(lambda m: m.is_invoice()).mapped("invoice_line_ids"):
            if line.price_unit <= 0 and line.display_type not in ("line_section","line_note"):
                from_loyalty = self.env.context.get('from_loyalty', False)
                if (
                    self.env.company.sale_discount_product_id
                    and line.product_id == self.env.company.sale_discount_product_id
                ):
                    continue
                if not from_pos and not from_loyalty:
                    raise ValidationError(_("An invoice cannot have a line with a price of zero"))

    @api.onchange("move_type")
    def _onchange_move_type(self):
        if self.move_type == "out_invoice":
            self.invoice_date = fields.Date.today()

    def action_post(self):
        
        for record in self:
            if record.move_type in ("out_invoice", "in_invoice", "out_refund", "in_refund"):
                for line in record.invoice_line_ids:
                    if line.display_type in ("line_section", "line_note"):
                        continue
                    if not line.tax_ids:
                        raise ValidationError(_("Add a tax to each product line. You cannot confirm the invoice if any product line is missing a tax."))

            sequence = record.env["ir.sequence"].sudo().search([("code", "=", "invoice.correlative"), ("company_id", "=", self.env.company.id)])
            correlative = str(sequence.number_next_actual).zfill(sequence.padding)

            invoices = record.env['account.move'].sudo().search([("correlative","=",correlative),('move_type', 'in',["out_invoice","out_refund"])])

            if invoices and record.move_type in ["out_invoice","out_refund"]:
                raise ValidationError(_("An invoice already exists with the Control Number: %s" % correlative))
        return super().action_post()

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves:
            if move.is_purchase_international and move.declaration_unique_of_customs and not move.correlative:
                move.correlative = move.declaration_unique_of_customs
        return moves

    @api.constrains("correlative", "is_contingency")
    def _check_correlative(self):
        AccountMove = self.env["account.move"]
        is_series_invoicing_enabled = self.company_id.group_sales_invoicing_series
        for move in self:
            if not move.is_contingency:
                continue
            if not is_series_invoicing_enabled and not move.correlative:
                raise ValidationError(
                    _(
                        "Contingency journal's invoices should always have a correlative if series "
                        "invoicing is not enabled"
                    )
                )
            repeated_moves = AccountMove.search(
                [
                    ("is_contingency", "=", True),
                    ("id", "!=", move.id),
                    ("correlative", "!=", False),
                    ("correlative", "=", move.correlative),
                    ("journal_id", "=", move.journal_id.id),
                ],
                limit=1,
            )
            if repeated_moves:
                raise UserError(
                    _("The correlative must be unique per journal when using a contingency journal")
                )
    @api.depends('journal_id')
    def _compute_is_debit_journal(self):
        for move in self:
            move.is_debit_journal = move.journal_id.is_debit if move.journal_id else False

    @api.depends("amount_residual")
    def _compute_payment_dates(self):
        def clear_dates(move):
            move.last_payment_date = False
            move.first_payment_date = False

        for move in self:
            if not move.is_invoice(include_receipts=True) and move.state != "posted":
                clear_dates(move)
                continue

            is_invoice_payment_widget = bool(move.invoice_payments_widget)
            if not is_invoice_payment_widget:
                clear_dates(move)
                continue

            payments = move.invoice_payments_widget
            if not payments or not payments.get("content", False):
                clear_dates(move)
                continue

            last_date = False
            first_date = False

            dates = list()

            for payment in payments.get("content"):
                if not self.validate_payment(payment):
                    continue

                dates.append(payment.get("date", False))

            if len(dates) > 0:
                last_date = fields.Date.from_string(max(dates))
                first_date = fields.Date.from_string(min(dates))

            move.last_payment_date = last_date
            move.first_payment_date = first_date

    @api.model
    def validate_payment(self, payment):
        """This function was created to validate payments through external modules"""
        return True

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

    @api.depends("payment_term_details")
    def _compute_next_installment_date(self):
        lang = self.env["res.lang"].search([("code", "=", self.env.user.lang)])
        date_format = lang.date_format if lang else "%Y-%m-%d"
        for invoice in self:
            invoice.next_installment_date = False
            if not invoice.payment_term_details:
                invoice.next_installment_date = invoice.invoice_date_due
                continue
            for term in invoice.payment_term_details:
                term_date = datetime.strptime(term.get("date", ""), date_format).date()
                if term_date and term_date >= fields.Date.today():
                    invoice.next_installment_date = term_date
                    break
    
    @api.depends("invoice_date", "state")
    def _compute_display_date_warning(self):
        today = fields.Date.context_today(self)
        for move in self:
            move.display_date_warning = bool(
                move.invoice_date and move.state == "draft" and move.invoice_date < today
            )

    def _post(self, soft=True):
        # Filtramos para asegurarnos de que solo intentamos publicar lo que está en borrador
        # Esto evita el error de "debe ser un borrador" en procesos automáticos
        draft_moves = self.filtered(lambda m: m.state == 'draft')
        
        # Si no hay nada en borrador (porque ya se publicó en un paso previo), 
        # devolvemos el self original para no romper el flujo.
        if not draft_moves:
            return self

        res = super(AccountMove, draft_moves)._post(soft)
        
        for move in res:
            # Solo aplicamos número de control a facturas de cliente/notas crédito
            # Evitamos tocar asientos de diferencia de cambio (entry) o pagos
            if move.is_invoice(include_receipts=True):
                if "invoice_print_type" in move.company_id._fields:
                    invoice_print_type = move.company_id.invoice_print_type
                else:
                    invoice_print_type = None
                
                if move.is_valid_to_sequence() and invoice_print_type != "fiscal":
                    move.correlative = move.get_sequence()
                    
        return res
        

    @api.model
    def is_valid_to_sequence(self) -> bool:
        """
        Check if the invoice satisfies the conditions to associate a new sequence number to its
        correlative.

        Returns:
            True or False whether the invoice already has a sequence number or not.
        """
        
        is_contingency = self.journal_id.is_contingency
        journal_type = self.journal_id.type == "sale"
        is_series_invoicing_enabled = self.company_id.group_sales_invoicing_series
        is_valid = (
            not self.correlative
            and journal_type
            and (not is_contingency or is_series_invoicing_enabled)
        )

        return is_valid

    @api.model
    def get_sequence(self):
        """
        Allows the invoice to have both a generic sequence
        number or a specific one given certain conditions.

        Returns
        -------
            The next number from the sequence to be assigned.
        """

        self.ensure_one()
        is_series_invoicing_enabled = self.company_id.group_sales_invoicing_series
        sequence = self.env["ir.sequence"].sudo()
        correlative = None

        if is_series_invoicing_enabled:
            correlative = self.journal_id.series_correlative_sequence_id

            if not correlative:
                raise UserError(_("The sale's series sequence must be in the selected journal."))
            return correlative.next_by_id()

        correlative = sequence.search(
            [("code", "=", "invoice.correlative"), ("company_id", "=", self.env.company.id)]
        )
        if not correlative:
            correlative = sequence.create(
                {
                    "name": "Número de control",
                    "code": "invoice.correlative",
                    "padding": 5,
                }
            )
        return correlative.next_by_id()


    def action_debit_note_button(self):
        action = ""
        for picking in self:
            action = picking.env.ref('account_debit_note.action_view_account_move_debit').read()[0]
        return action

    def write(self, vals):
        res = super().write(vals)
        for move in self:
            if move.is_purchase_international and move.declaration_unique_of_customs:
                if move.correlative != move.declaration_unique_of_customs:
                    move.correlative = move.declaration_unique_of_customs
            elif not move.is_purchase_international and move.correlative and move.correlative == move.declaration_unique_of_customs:
                move.correlative = False
                move.declaration_unique_of_customs = False
        return res
