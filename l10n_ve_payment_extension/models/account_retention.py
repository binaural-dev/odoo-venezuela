from odoo import api, models, fields, Command, _
from datetime import datetime
import re
from odoo.exceptions import UserError, ValidationError
from ..utils.utils_retention import load_retention_lines, search_invoices_with_taxes
from collections import defaultdict
import json
from odoo.tools.float_utils import float_round
import logging

_logger = logging.getLogger(__name__)


class AccountRetention(models.Model):
    _name = "account.retention"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Retention"
    _check_company_auto = True

    @api.depends('name', 'number')
    def _compute_display_name(self):
        for record in self:
            name = record.number or record.name or "/"
            record.display_name = name
    
    company_currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id.id,
    )
    foreign_currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.foreign_currency_id.id,
    )
    base_currency_is_vef = fields.Boolean(
        default=lambda self: self.env.company.currency_id == self.env.ref("base.VEF"),
    )

    is_third_party_retention = fields.Boolean(
        string="Third Party Billing",
        default=False,
        help="Indicates if this retention was created via the third-party billing flow.",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    name = fields.Char(
        "Description",
        size=64,
        default="/",
        states={"draft": [("readonly", False)]},
        help="Description of the withholding voucher",
    )
    code = fields.Char(
        size=32,
        states={"draft": [("readonly", False)]},
        help="Code of the withholding voucher",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("emitted", "Emitted"), ("cancel", "Cancelled")],
        index=True,
        default="draft",
        help="Status of the withholding voucher",
        tracking=True,
    )
    type_retention = fields.Selection(
        [
            ("iva", "IVA"),
            ("islr", "ISLR"),
            ("municipal", "Municipal"),
        ],
        required=True,
    )
    type = fields.Selection(
        [
            ("out_invoice", "Out invoice"),
            ("in_invoice", "In invoice"),
            ("out_refund", "Out refund"),
            ("in_refund", "In refund"),
            ("out_debit", "Out debit"),
            ("in_debit", "In debit"),
            ("out_contingence", "Out contingence"),
            ("in_contingence", "In contingence"),
        ],
        "Type retention",
        help="Tipo del Comprobante",
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        "Social reason",
        required=True,
        states={"draft": [("readonly", False)]},
        help="Social reason",
        tracking=True,
    )
    number = fields.Char("Voucher Number")
    correlative = fields.Char(readonly=True)
    date = fields.Date(
        "Voucher Date",
        states={"draft": [("readonly", False)]},
        help="Date of issuance of the withholding voucher by the external party.",
        default=fields.Date.context_today,
    )
    date_accounting = fields.Date(
        "Accounting Date",
        states={"draft": [("readonly", False)]},
        default=fields.Date.context_today,
        help=(
            "Date of arrival of the document and date to be used to make the accounting record."
            " Keep blank to use current date."
        ),
    )
    allowed_lines_move_ids = fields.Many2many(
        "account.move",
        compute="_compute_allowed_lines_move_ids",
        help=(
            "Technical field to store the allowed move types for the ISLR retention lines. This is"
            " used to filter the moves that can be selected in the ISLR retention lines."
        ),
    )

    retention_line_ids = fields.One2many(
        "account.retention.line",
        "retention_id",
        "retention line",
        states={"draft": [("readonly", False)]},
        help="Retentions",
    )

    code_visible = fields.Boolean(related="company_id.code_visible")

    payment_ids = fields.One2many(
        "account.payment",
        "retention_id",
        help="Payments",
    )

    total_invoice_amount = fields.Float(
        string="Taxable Income",
        compute="_compute_totals",
        help="Taxable Income Total",
        store=True,
    )
    total_iva_amount = fields.Float(
        string="Total IVA", compute="_compute_totals", store=True
    )
    total_retention_amount = fields.Float(
        compute="_compute_totals",
        store=True,
        help="Retained Amount Total",
    )

    foreign_total_invoice_amount = fields.Float(
        string="Taxable Income",
        compute="_compute_totals",
        help="Taxable Income Total",
        store=True,
    )
    foreign_total_iva_amount = fields.Float(
        string="Total IVA", compute="_compute_totals", store=True
    )
    foreign_total_retention_amount = fields.Float(
        compute="_compute_totals",
        store=True,
        help="Retained Amount Total",
    )
    original_lines_per_invoice_counter = fields.Char(
        help=(
            "Technical field to store the quantity of retention lines per invoice before the user"
            " changes them. This is used to know if the user has deleted the retention lines when"
            " the invoice is changed, in order to delete all the other lines of the same invoice"
            " that the one that just has been deleted."
        )
    )
    actual_invoice_ids = fields.Many2many("account.move", string="Actual Invoices", compute="_compute_actual_invoice_ids")  
    available_invoice_ids = fields.Many2many("account.move", string="Available Invoices")

    date_emision = fields.Date('Emision Date', default=False)

    @api.depends("retention_line_ids", "retention_line_ids.move_id")
    def _compute_actual_invoice_ids(self):
        for retention in self:
            retention.actual_invoice_ids = retention.retention_line_ids.mapped('move_id').ids

    @api.depends("type", "partner_id")
    def _compute_allowed_lines_move_ids(self):
        for retention in self:
            allowed_types = (
                ("in_invoice", "in_refund")
                if retention.type == "in_invoice"
                else ("out_invoice", "out_refund")
            )

            domain = [
                ("company_id", "=", self.env.company.id),
                ("state", "=", "posted"),
                ("partner_id", "=", retention.partner_id.id),
                ("move_type", "in", allowed_types),
            ]

            retention.allowed_lines_move_ids = self.env["account.move"].search(domain)

    @api.depends(
        "retention_line_ids.invoice_amount",
        "retention_line_ids.iva_amount",
        "retention_line_ids.retention_amount",
        "retention_line_ids.foreign_invoice_amount",
        "retention_line_ids.foreign_iva_amount",
        "retention_line_ids.foreign_retention_amount",
    )
    def _compute_totals(self):
        for retention in self:
            retention.total_invoice_amount = 0
            retention.total_iva_amount = 0
            retention.total_retention_amount = 0
            retention.foreign_total_invoice_amount = 0
            retention.foreign_total_iva_amount = 0
            retention.foreign_total_retention_amount = 0

            for line in retention.retention_line_ids:
                if line.move_id.move_type in ("in_refund", "out_refund"):
                    retention.total_invoice_amount -= float_round(
                        line.invoice_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.total_iva_amount -= float_round(
                        line.iva_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.total_retention_amount -= float_round(
                        line.retention_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.foreign_total_invoice_amount -= float_round(
                        line.foreign_invoice_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                    retention.foreign_total_iva_amount -= float_round(
                        line.foreign_iva_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                    retention.foreign_total_retention_amount -= float_round(
                        line.foreign_retention_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                else:
                    retention.total_invoice_amount += float_round(
                        line.invoice_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.total_iva_amount += float_round(
                        line.iva_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.total_retention_amount += float_round(
                        line.retention_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.foreign_total_invoice_amount += float_round(
                        line.foreign_invoice_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                    retention.foreign_total_iva_amount += float_round(
                        line.foreign_iva_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                    retention.foreign_total_retention_amount += float_round(
                        line.foreign_retention_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )

    @api.onchange("partner_id")
    def onchange_partner_id(self):
        """
        Load retention lines from invoices with taxes when the partner changes for IVA retentions
        that are not posted.
        """
        # For third-party billing, just re-compute existing line amounts
        # using the new partner's withholding, without replacing lines
        self._validate_retention_journals()
        for retention in self.filtered(
            lambda r: r.state == "draft" and r.partner_id and r.retention_line_ids and r.is_third_party_retention
        ):
            retention.retention_line_ids._onchange_move_id()

        standard_retentions = self.filtered(lambda r: not r.is_third_party_retention)
        if not standard_retentions:
            return

        for retention in standard_retentions.filtered(
            lambda r: (r.state, r.type_retention) == ("draft", "iva") and r.partner_id
        ):
            if retention.type == "in_invoice":
                result = retention._load_retention_lines_for_iva_supplier_retention()
            else:
                result = retention._load_retention_lines_for_iva_customer_retention()
            return result

    def _load_retention_lines_for_iva_supplier_retention(self):
        self.ensure_one()
        self.date_accounting = fields.Date.today()
        search_domain = [
            ('iva_voucher_number', '=', False),
            ("company_id", "=", self.company_id.id),
            ("partner_id", "=", self.partner_id.id),
            ("state", "=", "posted"),
            ("move_type", "in", ("in_refund", "in_invoice")),
            ("amount_residual", ">", 0),
        ]
        invoices_with_taxes = search_invoices_with_taxes(
            self.env["account.move"], search_domain
        ).filtered(
            lambda i: not any(
                i.retention_iva_line_ids.filtered(
                    lambda l: l.state in ("draft", "emitted")
                )
            )
        )
        if not any(invoices_with_taxes):
            raise UserError(
                _("There are no invoices with taxes to be retained for the supplier.")
            )
        self.clear_retention()
        lines = load_retention_lines(invoices_with_taxes, self.env["account.retention"])

        lines_per_invoice_counter = defaultdict(int)
        for line in lines:
            lines_per_invoice_counter[str(line[2]["move_id"])] += 1

        self.available_invoice_ids = invoices_with_taxes.ids
        return {
            "value": {
                "retention_line_ids": lines,
                "original_lines_per_invoice_counter": json.dumps(
                    lines_per_invoice_counter
                ),
            }
        }

    def _load_retention_lines_for_iva_customer_retention(self):
        self.ensure_one()
        search_domain = [
            ('iva_voucher_number', '=', False),
            ("company_id", "=", self.company_id.id),
            ("partner_id", "=", self.partner_id.id),
            ("state", "=", "posted"),
            ("move_type", "in", ("out_refund", "out_invoice")),
            ("amount_residual", ">", 0),
        ]
        invoices_with_taxes = search_invoices_with_taxes(
            self.env["account.move"], search_domain
        ).filtered(
            lambda i: not any(
                i.retention_iva_line_ids.filtered(
                    lambda l: l.state in ("draft", "emitted")
                )
            )
        )
        if not any(invoices_with_taxes):
            raise UserError(
                _("There are no invoices with taxes to be retained for the customer.")
            )
        self.clear_retention()
        lines = load_retention_lines(invoices_with_taxes, self.env["account.retention"])

        lines_per_invoice_counter = defaultdict(int)
        for line in lines:
            lines_per_invoice_counter[str(line[2]["move_id"])] += 1

        self.available_invoice_ids = invoices_with_taxes.ids
        return {
            "value": {
                "retention_line_ids": lines,
                "original_lines_per_invoice_counter": json.dumps(
                    lines_per_invoice_counter
                ),
            }
        }

    def _validate_retention_journals(self):
        """
        Validate that the company has the journals configured for the retention type.
        """
        for retention in self:
            # IVA
            if (retention.type_retention, retention.type) == (
                "iva",
                "in_invoice",
            ) and not self.env.company.iva_supplier_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a supplier IVA retention journal configured."
                    )
                )
            if (retention.type_retention, retention.type) == (
                "iva",
                "out_invoice",
            ) and not self.env.company.iva_customer_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a customer IVA retention journal configured."
                    )
                )
            # ISLR
            if (retention.type_retention, retention.type) == (
                "islr",
                "in_invoice",
            ) and not self.env.company.islr_supplier_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a supplier ISLR retention journal configured."
                    )
                )
            if (retention.type_retention, retention.type) == (
                "islr",
                "out_invoice",
            ) and not self.env.company.islr_customer_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a customer ISLR retention journal configured."
                    )
                )
            # Municipal
            if (retention.type_retention, retention.type) == (
                "municipal",
                "in_invoice",
            ) and not self.env.company.municipal_supplier_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a supplier municipal retention journal configured."
                    )
                )
            if (retention.type_retention, retention.type) == (
                "municipal",
                "out_invoice",
            ) and not self.env.company.municipal_customer_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a customer municipal retention journal configured."
                    )
                )

    def clear_retention(self):
        """
        Clear retention lines and payments.
        """
        self.ensure_one()
        self.update(
            {
                "retention_line_ids": (
                    Command.clear()
                    if any(
                        isinstance(id, api.NewId)
                        for id in self.retention_line_ids.ids
                    )
                    else False
                ),
            }
        )
    
    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for retention in res:
            if retention.is_third_party_retention:
                moves = retention.retention_line_ids.mapped("move_id")
                if any(m.state != "posted" for m in moves):
                    raise UserError(_("You cannot create retentions for a draft or cancelled invoice."))
        res._set_sequence()
        return res

    def write(self, vals):
        res = super().write(vals)
        for retention in self:
            if retention.is_third_party_retention:
                moves = retention.retention_line_ids.mapped("move_id")
                if any(m.state != "posted" for m in moves):
                    raise UserError(_("You cannot modify retentions for a draft or cancelled invoice."))
      
        return res

    def unlink(self):
        for record in self:
            if record.state == "emitted":
                raise ValidationError(
                    _(
                        "You cannot delete a hold linked to a posted entry. It is necessary to cancel the retention before being deleted"
                    )
                )
        return super().unlink()
    

    def action_draft(self):
        self.ensure_one()
        self.write({"state": "draft"})
        if self.payment_ids:
            self.payment_ids.action_draft()

    def action_post(self):
        """
        Post the retention, validate amounts per invoice, generate the 
        corresponding payments in batch, and reconcile them.
        """
        today = datetime.now()
        is_automated = self.env.context.get('automated_action') or self.env.context.get('cron_id')

        for retention in self:
            retention_amounts_by_move = defaultdict(float)
            for line in retention.retention_line_ids:
                retention_amounts_by_move[line.move_id] += line.retention_amount

            for move, retention_amount in retention_amounts_by_move.items():
                invoice_total = abs(move.amount_residual_signed)
                if invoice_total < retention_amount:
                    error_msg = _(
                        "The retention amount (%s) cannot be greater than the invoice total signed amount (%s) for invoice %s."
                    ) % (round(retention_amount, 2), invoice_total, move.name)
                    
                    if is_automated:
                        retention.message_post(body=error_msg, category='exception')
                        return False 
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Error'),
                            'message': error_msg,
                            'sticky': False,         
                            'type': 'danger',       
                        }
                    }
            if retention.type in ["out_invoice", "out_refund", "out_debit"] and not retention.number:
                raise UserError(_("Insert a number for the retention"))
                
            if retention.type_retention == "iva" and (not retention.number or not re.fullmatch(r"\d{14}", retention.number)):
                raise ValidationError(_("IVA retention: Number must be exactly 14 numeric digits."))
                
            if retention.type_retention == "islr" and retention.type == "in_invoice":
                retention._validate_islr_retention()

        for retention in self:
            vals = {}
            if not retention.date_accounting: vals['date_accounting'] = today
            if not retention.date: vals['date'] = today
            if vals: retention.write(vals)

        self._create_payments_from_retention_lines()

        for retention in self:
            move_ids = retention.mapped("retention_line_ids.move_id")
            self.set_voucher_number_in_invoice(move_ids, retention)
            if retention.type in ["in_invoice", "in_refund", "in_debit"]:
                retention._set_sequence()
                self.set_voucher_number_in_invoice(move_ids, retention)

        self._reconcile_all_payments()
        self.write({"state": "emitted"})

    def _validate_islr_retention(self):
        """
        Validations for the ISLR retention before posting it.
        """
        self.ensure_one()
        if not self.env.company.islr_supplier_retention_journal_id:
            raise UserError(
                _("The company must have a journal for ISLR supplier retention.")
            )

        islr_retention = self.retention_line_ids
        invoice_amounts_by_move = defaultdict(float)

        for line in islr_retention.filtered(lambda rl: rl.state != "cancel"):
            invoice_amounts_by_move[line.move_id] += line.invoice_amount

        self.env['account.move']._check_retention_vs_move(islr_retention)

    def set_voucher_number_in_invoice(self, move, retention):
        if retention.type_retention == "iva":
            move.write({"iva_voucher_number": retention.number})
        elif retention.type_retention == "islr":
            move.write({"islr_voucher_number": retention.number})
        elif retention.type_retention == "municipal":
            move.write({"municipal_voucher_number": retention.number})

    def action_print_municipal_retention_xlsx(self):


        self.ensure_one()
        if not self.date_emision:
            self.write({'date_emision': fields.Date.today()})
        
            # 2. Forzamos el guardado para que la interfaz se actualice
            self.flush_recordset(['date_emision'])

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/get_xlsx_municipal_retention?&retention_id={self.id}",
            "target": "new",
        }

    def _set_sequence(self):
        for retention in self.filtered(lambda r: not r.number):
            sequence_number = ""
            if retention.type_retention == "iva":
                sequence_number = retention.get_sequence_iva_retention().next_by_id()
            elif retention.type_retention == "islr":
                sequence_number = retention.get_sequence_islr_retention().next_by_id()
            else:
                sequence_number = (
                    retention.get_sequence_municipal_retention().next_by_id()
                )
            correlative = f"{retention.date_accounting.year}{retention.date_accounting.month:02d}{sequence_number}"
            retention.name = correlative
            retention.number = correlative

    @api.model
    def get_sequence_iva_retention(self):
        sequence = self.env["ir.sequence"].search(
            [
                ("code", "=", "retention.iva.control.number"),
                ("company_id", "=", self.env.company.id),
            ]
        )
        if not sequence:
            sequence = self.env["ir.sequence"].create(
                {
                    "name": "Numero de control retenciones IVA",
                    "code": "retention.iva.control.number",
                    "padding": 8,
                }
            )
        return sequence

    @api.model
    def get_sequence_islr_retention(self):
        sequence = self.env["ir.sequence"].search(
            [
                ("code", "=", "retention.islr.control.number"),
                ("company_id", "=", self.env.company.id),
            ]
        )
        if not sequence:
            sequence = self.env["ir.sequence"].create(
                {
                    "name": "Numero de control retenciones ISLR",
                    "code": "retention.islr.control.number",
                    "padding": 5,
                }
            )
        return sequence

    def get_sequence_municipal_retention(self):
        sequence = self.env["ir.sequence"].search(
            [
                ("code", "=", "retention.municipal.control.number"),
                ("company_id", "=", self.env.company.id),
            ]
        )
        if not sequence:
            sequence = self.env["ir.sequence"].create(
                {
                    "name": "Numero de control retenciones Municipal",
                    "code": "retention.iva.control.number",
                    "padding": 5,
                }
            )
        return sequence

    def clear_retention_number(self):
        for rec in self:
            if not rec.retention_line_ids:
                continue
            invoices = rec.retention_line_ids.mapped('move_id')
            for invoice in invoices:
                if rec.type_retention == 'islr' and invoice.islr_voucher_number:
                    invoice.islr_voucher_number = False
                elif rec.type_retention == 'iva' and invoice.iva_voucher_number:
                    invoice.iva_voucher_number = False
                elif rec.type_retention == 'municipal' and invoice.municipal_voucher_number:
                    invoice.municipal_voucher_number = False

    def action_cancel(self):
        for rec in self:
            if rec.state == 'cancel':
                continue

            if rec.payment_ids:
                ctx = dict(self.env.context, bypass_retention_lock=True,force_delete=True)
                
                reconciled_lines = rec.payment_ids.mapped("move_id.line_ids").filtered(lambda l: l.reconciled)
                if reconciled_lines:
                    reconciled_lines.with_context(ctx).remove_move_reconcile()
                
                rec.payment_ids.with_context(ctx).action_draft()
                rec.payment_ids.with_context(ctx).action_cancel()
                rec.payment_ids.with_context(ctx).write({'retention_id': False, 'is_retention': False, 'payment_type_retention': False, 'retention_ref': False})
            
            rec.clear_retention_number()
            
            if rec.retention_line_ids:
                rec.retention_line_ids.with_context(bypass_retention_lock=True).write({'payment_id': False})
            
            rec.write({"state": "cancel", "payment_ids": [Command.clear()]})
            
        return True

    def _validate_islr_retention_fields(self):
        """
        Validates the partner has a type person and all the retention lines have a payment concept.
        """
        self.ensure_one()
        if not self.partner_id.type_person_id:
            raise UserError(_("Select a type person"))
        if not any(self.retention_line_ids.filtered(lambda l: l.payment_concept_id)):
            raise UserError(_("Select a payment concept"))

    def _reconcile_all_payments(self):
        """
        Reconcile all payments of the retention with the invoice lines 
        corresponding to each payment.
        """

        payments = self.mapped("payment_ids")
        if not payments:
            raise UserError(_("No payments found for reconciliation."))

        payments.action_post()

        account_type_map = {
            "supplier": "liability_payable",
            "customer": "asset_receivable",
        }

        for payment in payments:
            account_type = account_type_map.get(payment.partner_type)

            if not account_type:
                raise UserError(
                    _("Unknown partner type '%s' for payment reconciliation.") % payment.partner_type
                )

            lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type == account_type and abs(l.balance) > 0
            )
            if not lines:
                raise ValidationError(
                    _("No registered lines found in the move to reconcile.")
                )
            
            payment.retention_line_ids.move_id.js_assign_outstanding_line(lines[0].id)

    @api.model
    def compute_retention_lines_data(self, invoice_id, payment=None):
        """
        Computes the retention lines data for the given invoice.

        Params
        ------
        invoice_id: account.move
            The invoice for which the retention lines are computed.
        type_retention: tuple[str,str]
            The type of retention and the type of invoice.
        payment: account.payment
            The payment for which the retention lines are computed.

        Returns
        -------
        list[dict]
            The retention lines data.
        """
        tax_ids = invoice_id.invoice_line_ids.filtered(
            lambda l: l.tax_ids and l.tax_ids[0].amount > 0
        ).mapped("tax_ids")
        if not any(tax_ids):
            raise UserError(_("The invoice %s has no tax."), invoice_id.number)

        withholding_amount = invoice_id.partner_id.withholding_type_id.value
        lines_data = []
        tax_groups = invoice_id.tax_totals["subtotals"][0]["tax_groups"]
        for tax_group in tax_groups:
            taxes = tax_ids.filtered(lambda l: l.tax_group_id.id == tax_group["id"])
            if not taxes:
                continue
            tax = taxes[0]
            retention_amount = tax_group["tax_amount"] * (withholding_amount / 100)
            line_data = {
                "name": _("Iva Retention"),
                "invoice_type": invoice_id.move_type,
                "move_id": invoice_id.id,
                "payment_id": payment.id if payment else None,
                "aliquot": tax.amount,
                "iva_amount": tax_group["tax_amount"],
                "invoice_total": invoice_id.tax_totals["total_amount"],
                "related_percentage_tax_base": withholding_amount,
                "invoice_amount": tax_group["base_amount"],
                "foreign_currency_rate": invoice_id.foreign_rate,
                "foreign_invoice_amount": tax_group["base_amount_foreign_currency"],
                "foreign_iva_amount": tax_group["tax_amount_foreign_currency"],
                "foreign_invoice_total": invoice_id.tax_totals["total_amount_foreign_currency"],
            }
            if invoice_id.move_type == "out_invoice":
                line_data["retention_amount"] = 0.0
                line_data["foreign_retention_amount"] = 0.0
            else:
                line_data["retention_amount"] = retention_amount
                line_data["foreign_retention_amount"] = float_round(
                    (line_data["foreign_iva_amount"] * (withholding_amount / 100)),
                    precision_digits=invoice_id.company_id.foreign_currency_id.decimal_places,
                    rounding_method='HALF-UP'
                ) #Acá siempre que la tercera posición decimal sea 5 o mayor se redondea hacia arriba. ATT DANIELA
            lines_data.append(line_data)
        return lines_data

    def get_signature(self):
        config = self.env["signature.config"].search(
            [("active", "=", True), ("company_id", "=", self.company_id.id)],
            limit=1,
        )
        if config and config.signature:
            return config.signature.decode()
        else:
            return False

    @api.constrains("number", "type")
    def _check_number(self):
        for record in self:
            if (
                record.type == "out_invoice"
                and record.number
                and record.state != "draft"
            ):
                if not re.fullmatch(r"\d{14}", record.number):
                    raise ValidationError(
                        _("The number must be exactly 14 numeric digits.")
                    )
                
    @api.model
    def default_get(self, fields_list):
        res = super(AccountRetention, self).default_get(fields_list)

        islr_lines_data = self.env.context.get('default_islr_lines')
        move_id = self.env.context.get('default_invoice_id')
        ret_type = self.env.context.get('default_type')
        multi = self.env.context.get('multi',False)

        if islr_lines_data and move_id and not multi:
            line_commands = []
            for line_data in islr_lines_data:
                concept_id, base_amount, invoice_line_id = line_data
                line_vals = {
                    'move_id': move_id,
                    'payment_concept_id': concept_id, 
                    'invoice_type': str(ret_type),
                    'invoice_amount': base_amount, 
                }
                line_commands.append(Command.create(line_vals))
            res['retention_line_ids'] = line_commands
        
        elif multi:
            line_commands = []
            for line_data in islr_lines_data:
                concept_id, base_amount, invoice_line_id = line_data
                actual_move_id = self.env['account.move.line'].browse(invoice_line_id).move_id.id
                line_vals = {
                    'move_id': actual_move_id,
                    'payment_concept_id': int(concept_id),
                    'invoice_type': str(ret_type),
                    'invoice_amount': base_amount,
                 }
                line_commands.append(Command.create(line_vals))
            res['retention_line_ids'] = line_commands
        
        return res

    def _create_payments_from_retention_lines(self):
        """
        Unified method to create payments from retention lines for IVA, ISLR, and Municipal.
        ALWAYS groups retention lines by invoice (move_id) to process them in optimal batches.
        """
        Payment = self.env["account.payment"]
        Rate = self.env["res.currency.rate"]

        for retention in self:
            if any(retention.payment_ids):
                continue
            
            if retention.type_retention == "islr":
                retention._validate_islr_retention_fields()

            lines_by_move = defaultdict(lambda: self.env["account.retention.line"])
            for line in retention.retention_line_ids:
                lines_by_move[line.move_id] += line

            payment_vals_list = []
            lines_to_link_by_vals = {}

            for move, lines in lines_by_move.items():
                
                vals = retention._prepare_retention_payment_vals(move, lines)
                
                if retention.type_retention == "iva":
                    vals["foreign_rate"] = lines[0].foreign_currency_rate
                    vals["foreign_inverse_rate"] = Rate.compute_inverse_rate(vals["foreign_rate"])
                else:
                    vals["foreign_rate"] = move.foreign_rate
                    vals["foreign_inverse_rate"] = move.foreign_inverse_rate

                payment_vals_list.append(vals)
                lines_to_link_by_vals[id(vals)] = lines

            if payment_vals_list:
                created_payments = Payment.create(payment_vals_list)

                retention.write({
                    "payment_ids": [Command.link(pay.id) for pay in created_payments]
                })
                
                for vals, payment in zip(payment_vals_list, created_payments):
                    associated_lines = lines_to_link_by_vals.get(id(vals))
                    if associated_lines:
                        
                        payment.write({"retention_line_ids": [Command.link(l.id) for l in associated_lines]})
                
                created_payments.compute_retention_amount_from_retention_lines()

    def _prepare_retention_payment_vals(self, move, lines):
        """
        Prepares the base dictionary values for creating an account.payment.
        INHERIT this method in other modules to inject new/custom fields easily.
        """
        self.ensure_one()
        has_subsidiary = "subsidiary" in self.env.company._fields
        is_supplier = self.type == "in_invoice"
        refund_type = "in_refund" if is_supplier else "out_refund"

        is_refund = move.move_type == refund_type
        p_type = "inbound" if is_refund == is_supplier else "outbound"
        p_method = "manual_in" if p_type == "inbound" else "manual_out"

        journals = {
            ("iva", "in_invoice"): self.env.company.iva_supplier_retention_journal_id,
            ("iva", "out_invoice"): self.env.company.iva_customer_retention_journal_id,
            ("islr", "in_invoice"): self.env.company.islr_supplier_retention_journal_id,
            ("islr", "out_invoice"): self.env.company.islr_customer_retention_journal_id,
            ("municipal", "in_invoice"): self.env.company.municipal_supplier_retention_journal_id,
            ("municipal", "out_invoice"): self.env.company.municipal_customer_retention_journal_id,
        }
        journal = journals.get((self.type_retention, self.type))

        res = {
            "state": "draft",
            "payment_type": p_type,
            "partner_type": "supplier" if is_supplier else "customer",
            "partner_id": move.partner_id.id,
            "journal_id": journal.id if journal else False,
            "payment_type_retention": self.type_retention,
            "payment_method_id": self.env.ref(f"account.account_payment_method_{p_method}").id,
            "is_retention": True,
            "currency_id": self.env.company.currency_id.id,
            "date": self.date_accounting
        }
        
        if not is_refund and has_subsidiary and self.env.company.subsidiary:
            res["account_analytic_id"] = move.account_analytic_id.id

        return res
