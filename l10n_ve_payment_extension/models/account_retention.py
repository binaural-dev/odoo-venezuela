from odoo import api, models, fields, Command, _
import re
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero, float_compare
from odoo.addons.account.models.account_move import BYPASS_LOCK_CHECK
from ..utils.utils_retention import load_retention_lines, search_invoices_with_taxes
from collections import defaultdict
import json
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
        help="Description of the withholding voucher",
    )
    code = fields.Char(
        size=32,
        help="Code of the withholding voucher",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("emitted", "Emitted"), ("cancel", "Cancelled")],
        index=True,
        default="draft",
        help="Status of the withholding voucher",
        tracking=True,
        copy=False,
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
        help="Social reason",
        tracking=True,
    )
    number = fields.Char("Voucher Number", copy=False)
    correlative = fields.Char(readonly=True, copy=False)
    date = fields.Date(
        "Voucher Date",
        help="Date of issuance of the withholding voucher by the external party.",
        default=fields.Date.context_today,
    )
    date_accounting = fields.Date(
        "Accounting Date",
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
        help="Retentions",
        copy=False,
    )

    code_visible = fields.Boolean(related="company_id.code_visible")

    payment_ids = fields.One2many(
        "account.payment",
        "retention_id",
        help="Payments",
        copy=False,
    )

    total_invoice_amount = fields.Monetary(
        currency_field="company_currency_id",
        string="Taxable Income",
        compute="_compute_totals",
        help="Taxable Income Total",
        store=True,
    )
    total_iva_amount = fields.Monetary(
        currency_field="company_currency_id",
        string="Total IVA", compute="_compute_totals", store=True
    )
    total_retention_amount = fields.Monetary(
        currency_field="company_currency_id",
        compute="_compute_totals",
        store=True,
        help="Retained Amount Total",
    )

    foreign_total_invoice_amount = fields.Monetary(
        currency_field="foreign_currency_id",
        string="Taxable Income",
        compute="_compute_totals",
        help="Taxable Income Total",
        store=True,
    )
    foreign_total_iva_amount = fields.Monetary(
        currency_field="foreign_currency_id",
        string="Total IVA", compute="_compute_totals", store=True
    )
    foreign_total_retention_amount = fields.Monetary(
        currency_field="foreign_currency_id",
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

    @api.depends("type", "type_retention", "partner_id")
    def _compute_allowed_lines_move_ids(self):
        for retention in self:
            allowed_types = (
                ("in_invoice", "in_refund", "in_debit")
                if retention.type in ("in_invoice", "in_refund", "in_debit", "in_contingence")
                else ("out_invoice", "out_refund", "out_debit")
            )

            domain = [
                ("company_id", "=", self.env.company.id),
                ("state", "=", "posted"),
                ("partner_id", "=", retention.partner_id.id),
                ("move_type", "in", allowed_types),
            ]

            if retention.type_retention == "islr":
                domain.append(("is_isrl_retention_available", "=", True))

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

                retention.total_invoice_amount += line.invoice_amount

                retention.total_iva_amount += line.iva_amount

                retention.total_retention_amount += line.retention_amount

                retention.foreign_total_invoice_amount += line.foreign_invoice_amount

                retention.foreign_total_iva_amount += line.foreign_iva_amount

                retention.foreign_total_retention_amount += line.foreign_retention_amount


    @api.onchange("partner_id")
    def onchange_partner_id(self):
        """
        Load retention lines from invoices with taxes when the partner changes for IVA retentions
        that are not posted. For ISLR/municipal retentions, existing lines are cleared instead,
        since they were picked from the previous partner's invoices and no longer apply.
        """
        self._validate_retention_journals()

        for retention in self.filtered(lambda r: r.state == "draft" and r.partner_id):
            if retention.is_third_party_retention:
                # For third-party billing, just re-compute existing line amounts
                # using the new partner's withholding, without replacing lines
                if retention.retention_line_ids:
                    retention.retention_line_ids._onchange_move_id()
            elif retention.type_retention == "iva":
                if retention.type in ["in_invoice", "in_refund", "in_debit"]:
                    return retention._load_retention_lines_for_iva_supplier_retention()
                return retention._load_retention_lines_for_iva_customer_retention()
            elif retention.retention_line_ids:
                retention.clear_retention()

    def _load_retention_lines_for_iva_supplier_retention(self):
        self.ensure_one()
        # Use the user's local "today" (not UTC) - _check_dates_not_in_future
        # compares date_accounting against fields.Date.context_today too,
        # and a UTC "today" can already be tomorrow while the user's local
        # calendar day hasn't rolled over yet (e.g. Caracas, UTC-4, from
        # 20:00 local onward), which would falsely reject this same value.
        self.date_accounting = fields.Date.context_today(self)
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
        # date_accounting/date are Date fields checked against the user's
        # local "today" by _check_dates_not_in_future() - using UTC
        # datetime.now() here could stamp tomorrow's date while the user's
        # local calendar day hasn't rolled over yet (e.g. Caracas, UTC-4,
        # from 20:00 local onward), making this fallback fail the very
        # constraint it's about to trigger on write() a few lines below.
        today = fields.Date.context_today(self)
        is_automated = self.env.context.get('automated_action') or self.env.context.get('cron_id')

        for retention in self:
            retention._check_duplicate_retention_lines()

            retention_amounts_by_move = defaultdict(float)
            for line in retention.retention_line_ids:
                retention_amounts_by_move[line.move_id] += line.retention_amount

            for move, retention_amount in retention_amounts_by_move.items():
                invoice_total = abs(move.amount_residual_signed)
                if invoice_total < retention_amount:
                    error_msg = _(
                        "The retention amount (%s) cannot be greater than the invoice total signed amount (%s) for invoice %s."
                    ) % (retention_amount, invoice_total, move.name)

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
            zero_retention_lines = retention.retention_line_ids.filtered(
                lambda l: float_is_zero(l.retention_amount, precision_rounding=self.company_currency_id.rounding)
            )
            if zero_retention_lines:
               
                error_msg = _("You can not create a retention with 0 amount.")
                if is_automated:
                    retention.message_post(body=error_msg, category='exception')
                    return False
                raise ValidationError(error_msg)

            if retention.type in ["out_invoice", "out_refund", "out_debit"] and not retention.number:
                raise UserError(_("Insert a number for the retention"))

            if retention.type_retention == "iva" and (not retention.number or not re.fullmatch(r"\d{14}", retention.number)):
                raise ValidationError(_("IVA retention: Number must be exactly 14 numeric digits."))

            if retention.type_retention == "islr" and retention.type in ["in_invoice", "in_refund", "in_debit"]:
                retention._validate_islr_retention()

            try:
                retention._check_accounting_date_vs_invoices()
                retention._check_dates_not_in_future()
            except ValidationError as e:
                if is_automated:
                    retention.message_post(body=str(e), category='exception')
                    return False
                raise

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

    def _check_duplicate_retention_lines(self):
        """
        Prevent the same invoice from being retained twice with the exact
        same differentiator - both within this retention (helpdesk #14548)
        and across any OTHER already-emitted retention of the same type -
        and reject lines whose declared differentiator does not actually
        exist on the invoice they claim to retain from:

        - ISLR: the invoice (move_id) can legitimately repeat across lines
          both when each line is for a different payment_concept_id, and
          when several products on the invoice share the SAME concept (the
          standard auto-generation flow from an invoice creates one line per
          invoice line, not one per concept - see
          account_move._get_payment_concepts_from_invoice). So instead of
          forbidding any repeat of (move_id, payment_concept_id), the sum of
          invoice_amount declared across lines sharing that combination -
          in this retention AND in any other emitted retention - must not
          exceed the real taxable base of the invoice for that concept (sum
          of price_subtotal of the invoice lines whose product has that
          payment_concept). The declared payment_concept_id must also match
          a product actually billed on that invoice.
        - IVA: the invoice can legitimately repeat when each line has a
          different real tax rate (aliquot). The same (move_id, aliquot)
          combination must not repeat - in this retention or in any other
          emitted retention - and the declared aliquot must match a tax
          actually applied on that invoice.
        - Municipal: the invoice can legitimately repeat when each line is
          for a different economic activity of the partner. The same
          (move_id, economic_activity_id) combination must not repeat - in
          this retention or in any other emitted retention.

        Only other retentions already in state 'emitted' are considered -
        two drafts referencing the same invoice/differentiator can coexist
        harmlessly as long as only one of them ever gets confirmed; the
        conflict only matters once one side is already final.

        Applies to any legal document/retention type - client
        (out_invoice/out_refund/out_debit) and supplier
        (in_invoice/in_refund/in_debit) - for IVA, ISLR and Municipal
        retentions alike.
        """
        self.ensure_one()
        precision = self.company_currency_id.rounding or self.env.company.currency_id.rounding
        lines_with_move = self.retention_line_ids.filtered(lambda l: l.move_id)
        other_lines = self._get_other_emitted_retention_lines(lines_with_move.mapped("move_id"))

        if self.type_retention == "islr":
            self._check_islr_concept_amounts(lines_with_move, precision, other_lines)
        elif self.type_retention == "iva":
            self._check_iva_duplicate_lines(lines_with_move, precision, other_lines)
        elif self.type_retention == "municipal":
            self._check_municipal_duplicate_lines(lines_with_move, other_lines)

    def _get_other_emitted_retention_lines(self, moves):
        """
        Retention lines of other already-emitted retentions of the same
        type_retention, restricted to the invoices this retention is about
        to touch - used to seed the duplicate-detection accumulators so a
        conflict against an already-confirmed retention is caught too, not
        just conflicts within this retention.
        """
        self.ensure_one()
        if not moves:
            return self.env["account.retention.line"]
        return self.env["account.retention.line"].search([
            ("move_id", "in", moves.ids),
            ("retention_id", "!=", self.id),
            ("retention_id.state", "=", "emitted"),
            ("retention_id.type_retention", "=", self.type_retention),
        ])

    def _check_islr_concept_amounts(self, client_lines, precision, other_lines=None):
        """
        ISLR: several invoice lines can legitimately share the same
        payment_concept_id (that's how the module auto-generates retention
        lines from an invoice - one line per product, not one per concept),
        so the same (move_id, payment_concept_id) combination is allowed to
        repeat. What must never happen is the declared invoice_amount summed
        across those repeats - in this retention AND in any other emitted
        retention already holding a line for the same (move, concept) -
        exceeding the real taxable base the invoice actually has for that
        concept (sum of balance - the company-currency amount, not raw
        price_subtotal - of the invoice lines whose product carries that
        payment_concept) - that's how someone re-declaring the same
        product/amount to inflate the retention shows up.

        Special case: when only ONE invoice line carries the concept (mixed
        with unrelated goods), account.retention.line._get_islr_concept_base_amounts
        legitimately proposes either the product's own subtotal OR the
        whole invoice subtotal as the default base, depending on the
        company's islr_prioritize_product_subtotal_base setting - and the
        accountant can always edit invoice_amount by hand to use whichever
        of the two criteria applies. So for that case the cap accepts the
        larger of the two (max(whole invoice base, product subtotal)),
        instead of only the product's own subtotal.
        """
        declared_by_key = {}
        base_by_key = {}
        retention_by_key = {}

        for other_line in (other_lines or self.env["account.retention.line"]):
            concept = other_line.payment_concept_id
            if not concept:
                continue
            key = (other_line.move_id.id, concept.id)
            declared_by_key[key] = declared_by_key.get(key, 0.0) + other_line.invoice_amount
            retention_by_key.setdefault(key, other_line.retention_id)

        for line in client_lines:
            concept = line.payment_concept_id
            if not concept:
                continue
            move = line.move_id
            invoice_lines_for_concept = move.invoice_line_ids.filtered(
                lambda l: l.product_id.product_tmpl_id.payment_concept == concept
            )
            if not invoice_lines_for_concept:
                raise ValidationError(
                    _(
                        "The payment concept (%(concept)s) of the line for"
                        " invoice %(invoice)s does not match any product on"
                        " that invoice."
                    )
                    % {"concept": concept.display_name, "invoice": line.move_id.display_name}
                )
            key = (move.id, concept.id)
            if key not in base_by_key:
                # account.retention.line proposes the default base
                # (_get_islr_concept_base_amounts) using either the whole
                # invoice subtotal or just the product's own subtotal,
                # depending on islr_prioritize_product_subtotal_base - but
                # that flag only controls what gets auto-proposed on
                # automatic creation. Once created, the accountant may
                # deliberately edit invoice_amount to use whichever of the
                # two legitimate criteria applies, so the tope here must
                # accept either one explicitly, not just whichever the flag
                # happens to favor.
                concept_lines = move.invoice_line_ids.filtered(
                    lambda l: l.product_id.product_tmpl_id.type == "service"
                    and l.product_id.product_tmpl_id.payment_concept
                )
                if len(concept_lines) <= 1:
                    whole_invoice_base = move.tax_totals["base_amount"]
                    product_subtotal_base = sum(abs(l.balance) for l in concept_lines)
                    base_by_key[key] = max(whole_invoice_base, product_subtotal_base)
                else:
                    base_by_key[key] = sum(abs(l.balance) for l in invoice_lines_for_concept)
                declared_by_key.setdefault(key, 0.0)
            declared_by_key[key] += line.invoice_amount
            if float_compare(
                declared_by_key[key], base_by_key[key], precision_rounding=precision
            ) > 0:
                other_retention = retention_by_key.get(key)
                if other_retention:
                    raise ValidationError(
                        _(
                            "The taxable base declared for invoice %(invoice)s and payment"
                            " concept %(concept)s exceeds the actual base billed under that"
                            " concept, once what retention %(retention)s already retained"
                            " for it is taken into account."
                        )
                        % {
                            "invoice": line.move_id.display_name,
                            "concept": concept.display_name,
                            "retention": other_retention.display_name,
                        }
                    )
                raise ValidationError(
                    _(
                        "The taxable base declared across the lines of invoice"
                        " %(invoice)s for payment concept %(concept)s exceeds"
                        " the actual base billed under that concept on the"
                        " invoice."
                    )
                    % {"invoice": line.move_id.display_name, "concept": concept.display_name}
                )

    def _check_iva_duplicate_lines(self, client_lines, precision, other_lines=None):
        """
        IVA: compute_retention_lines_data generates at most one line per
        real tax_group on the invoice, so the same real tax must never
        appear in more than one line, whether in this retention or in any
        other already-emitted retention.
        """
        seen_keys = {}

        for other_line in (other_lines or self.env["account.retention.line"]):
            if float_is_zero(other_line.aliquot, precision_rounding=precision):
                continue
            taxes = other_line.move_id.invoice_line_ids.filtered(
                lambda l: l.tax_ids and l.tax_ids[0].amount > 0
            ).mapped("tax_ids").filtered(lambda t: t.amount == other_line.aliquot)
            tax_key = taxes[0].id if len(taxes) == 1 else round(other_line.aliquot, 2)
            seen_keys[(other_line.move_id.id, tax_key)] = other_line.retention_id

        for line in client_lines:
            if float_is_zero(line.aliquot, precision_rounding=precision):
                continue
            # Prefer the real account.tax id applied on the invoice for this
            # aliquot (same matching pattern used in _onchange_move_id) so
            # that two different taxes sharing a tax_group (or a rounded %)
            # are not confused; fall back to the rounded aliquot only if a
            # unique tax cannot be resolved from the invoice.
            taxes = line.move_id.invoice_line_ids.filtered(
                lambda l: l.tax_ids and l.tax_ids[0].amount > 0
            ).mapped("tax_ids").filtered(
                lambda t: t.amount == line.aliquot
            )
            if not taxes:
                raise ValidationError(
                    _(
                        "The tax rate (%(aliquot)s%%) of the line for invoice"
                        " %(invoice)s does not match any tax applied on that"
                        " invoice."
                    )
                    % {"aliquot": line.aliquot, "invoice": line.move_id.display_name}
                )
            tax_key = taxes[0].id if len(taxes) == 1 else round(line.aliquot, 2)
            key = (line.move_id.id, tax_key)
            if key in seen_keys:
                other_retention = seen_keys[key]
                if other_retention and other_retention != self:
                    raise ValidationError(
                        _(
                            "The invoice %(invoice)s was already retained at the same tax"
                            " rate (%(aliquot)s%%) by retention %(retention)s. Each"
                            " invoice/rate combination can only appear once."
                        )
                        % {
                            "invoice": line.move_id.display_name,
                            "aliquot": line.aliquot,
                            "retention": other_retention.display_name,
                        }
                    )
                raise ValidationError(
                    _(
                        "The invoice %(invoice)s is duplicated in this retention at the"
                        " same tax rate (%(aliquot)s%%). Each invoice/rate combination"
                        " can only appear once."
                    )
                    % {"invoice": line.move_id.display_name, "aliquot": line.aliquot}
                )
            seen_keys[key] = self

    def _check_municipal_duplicate_lines(self, lines, other_lines=None):
        """
        Municipal: the invoice can legitimately repeat when each line is for
        a different economic activity of the partner, so the same
        (move_id, economic_activity_id) combination must never repeat,
        whether in this retention or in any other already-emitted
        retention.
        """
        seen_keys = {}

        for other_line in (other_lines or self.env["account.retention.line"]):
            if not other_line.economic_activity_id:
                continue
            seen_keys[(other_line.move_id.id, other_line.economic_activity_id.id)] = other_line.retention_id

        for line in lines:
            if not line.economic_activity_id:
                continue
            key = (line.move_id.id, line.economic_activity_id.id)
            if key in seen_keys:
                other_retention = seen_keys[key]
                if other_retention and other_retention != self:
                    raise ValidationError(
                        _(
                            "The invoice %(invoice)s was already retained for the same"
                            " economic activity (%(activity)s) by retention %(retention)s."
                        )
                        % {
                            "invoice": line.move_id.display_name,
                            "activity": line.economic_activity_id.display_name,
                            "retention": other_retention.display_name,
                        }
                    )
                raise ValidationError(
                    _(
                        "The invoice %(invoice)s is duplicated in this retention for the"
                        " same economic activity (%(activity)s). Each invoice/activity"
                        " combination can only appear once."
                    )
                    % {"invoice": line.move_id.display_name, "activity": line.economic_activity_id.display_name}
                )
            seen_keys[key] = self

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
            # Dispatch through get_sequence_<type>_retention() rather than
            # calling get_sequence_retention() directly: modules like
            # binaural_subsidiary_payment_extension override
            # get_sequence_municipal_retention() to pick a per-subsidiary
            # sequence, and that override must still run here.
            sequence = getattr(
                retention, f"get_sequence_{retention.type_retention}_retention"
            )()
            retention._check_sequence_no_gap(sequence, retention.type_retention)
            sequence_number = sequence.next_by_id()
            correlative = f"{retention.date_accounting.year}{retention.date_accounting.month:02d}{sequence_number}"
            retention.name = correlative
            retention.number = correlative

    def _check_sequence_no_gap(self, sequence, type_retention):
        if sequence.implementation == "no_gap":
            return
        # A sequence can reach here through an external override (e.g.
        # binaural_subsidiary_payment_extension's per-subsidiary municipal
        # sequence, picked from a plain Many2one the user sets on the
        # subsidiary form) that this module's migration has no way to know
        # about -- it only touches the three sequences it owns directly.
        # Fix it on demand instead of blocking the user with an error they
        # can't normally act on (ir.sequence isn't editable by an
        # accounting user): same transition the migrate() script performs,
        # reading the counter predicted from the PostgreSQL sequence
        # *before* switching implementation, so the fiscal correlative
        # doesn't reset to 1.
        seq_sudo = sequence.sudo()
        next_actual = seq_sudo.number_next_actual or 1
        seq_sudo.write({"implementation": "no_gap", "number_next_actual": next_actual})
        _logger.info(
            "l10n_ve_payment_extension: sequence %r (id=%s) switched to "
            "no_gap on demand for a %s retention, continuing from counter "
            "%s.",
            sequence.name, sequence.id, type_retention, next_actual,
        )

    @api.model
    def get_sequence_retention(self, type_retention):
        """Get (or create) the ir.sequence for a given retention type.

        Fully driven by the `type_retention` selection: the sequence code
        and name are derived from it, so a new retention type only needs an
        entry in that selection to get its own sequence automatically.
        """
        code = f"retention.{type_retention}.control.number"
        sequence = self.env["ir.sequence"].with_context(active_test=False).search(
            [
                ("code", "=", code),
                ("company_id", "=", self.env.company.id),
            ],
            order="id asc",
            limit=1,
        )
        if not sequence:
            padding_by_type = {"iva": 8, "islr": 5, "municipal": 5}
            sequence = self.env["ir.sequence"].create(
                {
                    "name": _("Numero de control retenciones %s")
                    % type_retention.upper(),
                    "code": code,
                    "padding": padding_by_type.get(type_retention, 5),
                    "company_id": self.env.company.id,
                    "implementation": "no_gap",
                }
            )
        return sequence

    def get_sequence_iva_retention(self):
        return self.get_sequence_retention("iva")

    def get_sequence_islr_retention(self):
        return self.get_sequence_retention("islr")

    def get_sequence_municipal_retention(self):
        return self.get_sequence_retention("municipal")

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

        # These payments are dated with the retention's own date_accounting
        # (see _prepare_retention_payment_vals), which can already sit in a
        # closed fiscal period by the time the retention itself is processed --
        # bypass_lock_check is the core's own escape hatch for that check, only
        # triggered here by the state -> 'posted' transition (not by writing
        # 'date', which never happens after creation).
        payments.with_context(bypass_lock_check=BYPASS_LOCK_CHECK).action_post()

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
            
            # `l10n_ve_exchange_is_retention_reconcile` -- explicit,
            # module-owned context key (as opposed to reusing the native
            # `no_exchange_difference` alone) so that any OTHER module
            # hooking into reconciliation can tell a retention payoff
            # apart from any other legitimate reason a caller might set
            # `no_exchange_difference` (e.g. `l10n_ve_exchange_difference`
            # itself sets it when closing its own Debit/Credit Note,
            # `account_move_line.py::_create_exchange_difference_note`).
            # Coordinated purely via context, not a shared dependency:
            # `l10n_ve_exchange_difference` reads this key without
            # depending on this module.
            payment.retention_line_ids.move_id.with_context(
                no_exchange_difference=True,
                group_in_single_partial=True,
                l10n_ve_exchange_is_retention_reconcile=True,
            ).js_assign_outstanding_line(lines[0].id)

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
            retention_amount = abs(tax_group["tax_amount"] * (withholding_amount / 100))
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
            if invoice_id.move_type in ['out_invoice', 'out_refund']:
                if self.env.company.auto_fill_retention_amount_iva:
                    line_data["retention_amount"] = retention_amount
                    line_data["foreign_retention_amount"] = line_data["foreign_iva_amount"] * (withholding_amount / 100)

                else:
                    line_data["retention_amount"] = 0.0
                    line_data["foreign_retention_amount"] = 0.0
            else:
                line_data["retention_amount"] = retention_amount
                line_data["foreign_retention_amount"] = line_data["foreign_iva_amount"] * (withholding_amount / 100)
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

    def _get_max_invoice_date(self):
        self.ensure_one()
        invoice_dates = [
            date
            for date in (
                move.invoice_date_display or move.invoice_date
                for move in self.retention_line_ids.move_id
            )
            if date
        ]
        return max(invoice_dates) if invoice_dates else False

    def _check_accounting_date_vs_invoices(self):
        """
        Neither a retention's accounting date nor its voucher date can
        precede any of the invoices it withholds from: both are a
        consequence of an invoice already issued. The accounting-date rule
        was added for helpdesk #15019/#14984; helpdesk #15188 reported that
        the voucher date (date) was left uncovered - editing it to a date
        earlier than the invoice and approving the retention was silently
        allowed - so the same rule is extended here to cover it too.
        """
        for retention in self:
            max_invoice_date = retention._get_max_invoice_date()
            if not max_invoice_date:
                continue
            invalid_moves = retention.retention_line_ids.move_id.filtered(
                lambda move: (move.invoice_date_display or move.invoice_date) == max_invoice_date
            )
            invoice_name = ", ".join(
                move.name or move.ref or str(move.id) for move in invalid_moves
            )

            accounting_date = retention.date_accounting or fields.Date.context_today(retention)
            if accounting_date < max_invoice_date:
                raise ValidationError(
                    _(
                        "The accounting date (%(accounting_date)s) cannot be earlier than the "
                        "invoice date (%(invoice_date)s) for invoice %(invoice_name)s."
                    )
                    % {
                        "accounting_date": accounting_date,
                        "invoice_date": max_invoice_date,
                        "invoice_name": invoice_name,
                    }
                )

            voucher_date = retention.date
            if voucher_date and voucher_date < max_invoice_date:
                raise ValidationError(
                    _(
                        "The voucher date (%(voucher_date)s) cannot be earlier than the "
                        "invoice date (%(invoice_date)s) for invoice %(invoice_name)s."
                    )
                    % {
                        "voucher_date": voucher_date,
                        "invoice_date": max_invoice_date,
                        "invoice_name": invoice_name,
                    }
                )

    def _check_dates_not_in_future(self):
        """
        Neither the accounting date nor the voucher date can be later than
        today - a retention is issued for something already accrued, it
        cannot be dated in the future.
        """
        for retention in self:
            today = fields.Date.context_today(retention)
            if retention.date_accounting and retention.date_accounting > today:
                raise ValidationError(
                    _(
                        "The accounting date (%(date)s) cannot be later than today (%(today)s)."
                    )
                    % {"date": retention.date_accounting, "today": today}
                )
            if retention.date and retention.date > today:
                raise ValidationError(
                    _(
                        "The voucher date (%(date)s) cannot be later than today (%(today)s)."
                    )
                    % {"date": retention.date, "today": today}
                )

    @api.constrains("date_accounting", "date", "retention_line_ids")
    def _check_accounting_date(self):
        self._check_accounting_date_vs_invoices()
        self._check_dates_not_in_future()

    @api.constrains("number", "type")
    def _check_number(self):
        for record in self:
            if (
                record.type in ['out_invoice', 'out_refund']
                and record.number
                and record.state != "draft"
            ):
                if not re.fullmatch(r"\d{14}", record.number):
                    raise ValidationError(
                        _("The number must be exactly 14 numeric digits.")
                    )

    @api.constrains("number", "company_id", "type_retention")
    def _check_number_unique(self):
        for record in self.filtered("number"):
            duplicate = self.search([
                ("id", "!=", record.id),
                ("number", "=", record.number),
                ("company_id", "=", record.company_id.id),
                ("type_retention", "=", record.type_retention),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    _(
                        "Voucher number %(number)s is already used by another %(type_retention)s "
                        "retention (%(other)s) in this company."
                    )
                    % {
                        "number": record.number,
                        "type_retention": record.type_retention,
                        "other": duplicate.display_name,
                    }
                )

    @api.constrains("partner_id", "retention_line_ids", "is_third_party_retention")
    def _check_lines_match_partner(self):
        for retention in self.filtered(lambda r: not r.is_third_party_retention):
            mismatched = retention.retention_line_ids.filtered(
                lambda l: l.move_id and l.move_id.partner_id != retention.partner_id
            )
            if mismatched:
                raise ValidationError(
                    _(
                        "All retention lines must belong to invoices of %(partner)s. "
                        "Invoice(s) %(moves)s belong to a different partner."
                    )
                    % {
                        "partner": retention.partner_id.display_name,
                        "moves": ", ".join(mismatched.mapped("move_id.name")),
                    }
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
        is_supplier = self.type in ["in_invoice", "in_refund", "in_debit"]
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
        move_type = self.type

        # Si es Nota de Crédito (refund), lo tratamos como su factura equivalente para el diario
        if move_type in ["in_refund", "in_debit"]:
            move_type = 'in_invoice'
        elif move_type in ['out_refund' ,'out_debit']:
            move_type = 'out_invoice'

        journal = journals.get((self.type_retention, move_type))
        if not journal:
            raise UserError(_('There are not retention Journals config.'))

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

        # l10n_ve_igtf's js_assign_outstanding_line picks conversion_date over
        # payment.date for the advance-crossing move's date/rate unless this is
        # set, which would misprice the crossed amount against the retention's
        # own date_accounting. Guarded since l10n_ve_igtf isn't a hard dependency.
        if "keep_alter_value_vef" in self.env["account.payment"]._fields:
            res["keep_alter_value_vef"] = True

        return res
