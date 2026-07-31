import logging
from collections import defaultdict
from contextlib import contextmanager

from lxml import etree
from odoo import _, api, fields, models, Command
from odoo.exceptions import UserError, ValidationError
from odoo.tools import drop_index, float_compare, index_exists
from odoo.tools.float_utils import float_round
from odoo.tools.misc import formatLang

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    _sql_constraints = [
        (
            "unique_name",
            "",
            "Another entry with the same name already exists.",
        ),
        (
            "unique_name_ve",
            "",
            "Another entry with the same name already exists.",
        ),
    ]

    def _auto_init(self):
        res = super()._auto_init()
        if not index_exists(self.env.cr, "account_move_unique_name_ve"):
            drop_index(self.env.cr, "account_move_unique_name", self._table)
            # Make all values of `name` different (naming them `name (1)`, `name (2)`...) so that
            # we can add the following UNIQUE INDEX
            self.env.cr.execute(
                """
                WITH duplicated_sequence AS (
                    SELECT name, partner_id, state, journal_id
                    FROM account_move
                    WHERE state = 'posted'
                    AND name != '/'
                    AND move_type IN ('in_invoice', 'in_refund', 'in_receipt')
                GROUP BY partner_id, journal_id, name, state
                    HAVING COUNT(*) > 1
                ),
                to_update AS (
                    SELECT move.id,
                        move.name,
                        move.state,
                        move.date,
                        row_number() OVER(PARTITION BY move.name, move.partner_id, move.partner_id, move.date) AS row_seq
                        FROM duplicated_sequence
                        JOIN account_move move ON move.name = duplicated_sequence.name
                                            AND move.partner_id = duplicated_sequence.partner_id
                                            AND move.state = duplicated_sequence.state
                                            AND move.journal_id = duplicated_sequence.journal_id
                ),
                new_vals AS (
                    SELECT id,
                            name || ' (' || (row_seq-1)::text || ')' AS name
                        FROM to_update
                        WHERE row_seq > 1
                )
                UPDATE account_move
                SET name = new_vals.name
                FROM new_vals
                WHERE account_move.id = new_vals.id;
            """
            )

            self.env.cr.execute(
                """
                CREATE UNIQUE INDEX account_move_unique_name
                    ON account_move(
                        name, partner_id, company_id, journal_id
                    )
                WHERE state = 'posted' AND name != '/';
                CREATE UNIQUE INDEX account_move_unique_name_ve
                    ON account_move(
                        name, partner_id, company_id, journal_id
                    )
                WHERE state = 'posted' AND name != '/';
            """
            )
        return res

    def _get_fields_to_compute_lines(self):
        return ["invoice_line_ids", "line_ids", "foreign_inverse_rate", "foreign_rate"]

    def default_alternate_currency(self):
        """
        This method is used to get the foreign currency of the company and set it as the default
        value of the foreign currency field.

        Returns
        -------
        type = int
            The id of the foreign currency of the company
        """
        return self.env.company.currency_foreign_id.id or False

    foreign_currency_id = fields.Many2one(
        "res.currency",
        default=default_alternate_currency,
    )

    @api.onchange("move_type")
    def _onchange_move_type(self):
        self.invoice_date = False if self.move_type == "entry" else fields.Date.today()

    foreign_rate = fields.Float(
        compute="_compute_rate",
        store=True,
        digits="Tasa",
        tracking=True,
        readonly=False,
    )
    foreign_inverse_rate = fields.Float(
        help="Rate that will be used as factor to multiply of the foreign currency for this move.",
        compute="_compute_rate",
        store=True,
        index=True,
        readonly=False,
        digits=0,
    )

    manually_set_rate = fields.Boolean(default=False)
    last_foreign_rate = fields.Float(copy=False)

    vat = fields.Char(
        string="VAT",
        help="VAT of the partner",
        compute="_compute_vat",
    )

    financial_document = fields.Boolean(default=False, copy=False)

    foreign_taxable_income = fields.Monetary(
        help="Foreign Taxable Income of the invoice",
        compute="_compute_foreign_taxable_income",
        currency_field="foreign_currency_id",
    )
    total_taxed = fields.Many2one(
        "account.tax",
        help="Total Taxed of the invoice",
    )
    foreign_total_billed = fields.Monetary(
        help="Foreign Total Billed of the invoice",
        compute="_compute_foreign_total_billed",
        currency_field="foreign_currency_id",
        store=True,
    )

    detailed_amounts = fields.Binary(compute="_compute_detailed_amounts")

    foreign_debit = fields.Monetary(
        compute="_compute_total_debit_credit", currency_field="foreign_currency_id"
    )
    foreign_credit = fields.Monetary(
        compute="_compute_total_debit_credit", currency_field="foreign_currency_id"
    )
    foreign_balance = fields.Monetary(
        compute="_compute_total_debit_credit", currency_field="foreign_currency_id"
    )
    display_foreign_balance_warning = fields.Boolean(compute="_compute_total_debit_credit")
    real_portion_amount = fields.Monetary(currency_field="company_currency_id")
    real_portion_count = fields.Integer(default=0)
    
    foreign_inverse_rate_vef = fields.Float(compute="_compute_inverse_rate_vef",store=True)

    foreign_amount_residual = fields.Monetary(
        'Foreign Amount Residual',
        copy=False,
        compute='_compute_foreign_amount_residual',
        currency_field='foreign_currency_id',
        readonly=False,
    )

    @api.depends('line_ids.foreign_amount_residual')
    def _compute_foreign_amount_residual(self):
        for move in self:
            total_residual_currency = 0.0
            for line in move.line_ids:
                if line.display_type == 'payment_term':
                    total_residual_currency += line.foreign_amount_residual
            sign = move.direction_sign
            if move.is_invoice(include_receipts=True):
                move.foreign_amount_residual = -sign * total_residual_currency
            else:
                move.foreign_amount_residual = abs(total_residual_currency)

    @api.depends('invoice_date', 'date', 'company_id.currency_foreign_id')
    def _compute_inverse_rate_vef(self):
        Rate = self.env['res.currency.rate']
        for move in self:
            currency = move.company_id.currency_foreign_id
            rate = False

            if currency:
                date = move.invoice_date or move.date

                if date:
                    
                    rate = Rate.search([
                        ('currency_id', '=', currency.id),
                        ('name', '<=', date),
                    ], order='name desc', limit=1)

            move.foreign_inverse_rate_vef = rate.inverse_company_rate if rate else 0.0

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        context = self.with_context(active_test=False)
        return super(AccountMove, context).search_read(domain, fields, offset, limit, order)

    is_reset_to_draft_for_price_change = fields.Boolean(copy=False)



    @api.depends("line_ids.foreign_debit", "line_ids.foreign_credit")
    def _compute_total_debit_credit(self):
        for move in self:
            fc = move.company_id.currency_foreign_id
            if (
                move.is_invoice(include_receipts=True)
                and move.currency_id
                and move.currency_id != move.company_id.currency_id
                and fc
                and move.currency_id != fc
            ):
                total = move.currency_id._convert(
                    abs(move.amount_total),
                    fc,
                    move.company_id,
                    move.invoice_date or fields.Date.today(),
                )
                move.foreign_debit = total
                move.foreign_credit = total
            else:
                move.foreign_debit = sum(move.line_ids.mapped("foreign_debit"))
                move.foreign_credit = sum(move.line_ids.mapped("foreign_credit"))
            move.foreign_balance = move.foreign_debit - move.foreign_credit
            move.display_foreign_balance_warning = not move.foreign_currency_id.is_zero(move.foreign_balance)

    @api.depends("invoice_line_ids", "tax_totals")
    def _compute_detailed_amounts(self):
        for record in self:
            discount_amount = 0.0
            if not record.tax_totals:
                record.detailed_amounts = {}
                continue
            amount_taxed = record.tax_totals.get("amount_total", 0.0) - record.tax_totals.get("amount_untaxed", 0.0)
            total = 0.0
            for line in record.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
                subtotal = line.price_unit * line.quantity
                if line.discount > 0:
                    discount_amount += subtotal - line.price_subtotal
                total += subtotal
            record.detailed_amounts = {
                "gross_amount": total,
                "formatted_gross_amount": formatLang(self.env, total, currency_obj=record.currency_id),
                "discount_amount": discount_amount,
                "formatted_discount_amount": formatLang(self.env, discount_amount, currency_obj=record.currency_id),
                "gross_discount_amount": total - discount_amount,
                "formatted_gross_discount_amount": formatLang(self.env, total - discount_amount, currency_obj=record.currency_id),
                "taxes_amount": amount_taxed,
                "formatted_taxes_amount": formatLang(self.env, amount_taxed, currency_obj=record.currency_id),
            }


    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """
        This method is used to get the view of the account move form and add the foreign currency
        symbol to the page title.

        Parameters
        ----------
        view_id : int
            The id of the view

        view_type : str
            The type of the view

        options : dict
            The options of the view

        Returns
        -------
        type = dict
            The view of the account move form with the foreign currency symbol added to the page
            title.
        """
        foreign_currency_id = self.env.company.currency_foreign_id.id

        res = super().get_view(view_id, view_type, **options)

        if foreign_currency_id:
            foreign_currency_record = self.env["res.currency"].search(
                [("id", "=", int(foreign_currency_id))]
            )
            foreign_currency_symbol = foreign_currency_record.symbol or ""
            if view_type == "form":
                view_id = self.env.ref(
                    "l10n_ve_accountant.view_account_move_form_l10n_ve_accountant"
                ).id
                doc = etree.XML(res["arch"])
                page = doc.xpath("//page[@name='foreign_currency']")
                if page:
                    page[0].set(
                        "string", _("Foreign Currency ") + " " + foreign_currency_symbol
                    )
                    res["arch"] = etree.tostring(doc, encoding="unicode")
        return res

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)

        for move in moves:
            if move.move_type != "in_invoice":
                move._compute_rate()
            if move.move_type in ("out_refund", "in_refund") and move.reversed_entry_id:
                move.foreign_rate = move.reversed_entry_id.foreign_rate
                move.foreign_inverse_rate = move.reversed_entry_id.foreign_inverse_rate
            Rate = self.env["res.currency.rate"]
            rate_values = Rate.compute_rate(
                move.foreign_currency_id.id, move.invoice_date or fields.Date.today()
            )
            last_foreign_rate = rate_values.get("foreign_rate", 0)
            if move.manually_set_rate and move.foreign_rate != last_foreign_rate:
                move.message_post(
                    body=_(
                        "The rate has been updated from %(last_rate)s to %(rate)s ",
                    )
                    % ({"rate": move.foreign_rate, "last_rate": last_foreign_rate})
                )

        return moves

    def write(self, vals):
        if vals.get("foreign_rate", False):
            for move in self:
                vals.update({"last_foreign_rate": move.foreign_rate})
        res = super().write(vals)
        for move in self:
            if (
                vals.get("foreign_rate", False)
                and move.manually_set_rate
                and move.foreign_rate != move.last_foreign_rate
            ):
                move.message_post(
                    body=_(
                        "The rate has been updated from %(last_rate)s to %(rate)s ",
                    )
                    % ({"rate": move.foreign_rate, "last_rate": move.last_foreign_rate})
                )
        return res

    @api.constrains("invoice_line_ids")
    def _check_taxes_id(self):
        for moves in self:
            if moves.move_type == "entry":
                continue

            for line in moves.invoice_line_ids:
                if (
                    len(line.tax_ids) != 1
                    and line.display_type == "product"
                    and self.env.company.unique_tax
                ):
                    raise ValidationError(_("This product must have only one tax."))

    @api.constrains("currency_id")
    def _check_currency_id(self):
        for move in self.filtered(lambda m: m.is_invoice(include_receipts=True)):
            if move.currency_id.id != self.env.company.currency_id.id:
                raise ValidationError(
                    _("You cannot place a currency other than the base of the system.")
                )

    def legacy_compute_line_ids_foreign_debit_and_credit(self):
        """
        This method is used to compute the foreign debit and foreign credit of the line_ids field
        (journal entries) based on certain parameters.

        As each product line of the invoice lines has an equivalent in the journal entries, the
        foreign debit and foreign credit of the journal entries that corresponds to each invoice
        line will be the foreign subtotal of its equivalent product line.

        The tax lines of the journal entries does not have an equivalent on the invoice lines, so
        the foreign debit and foreign credit of the journal entries that corresponds to each tax
        will be the sum of the foreign subtotal of the lines from which the tax line is computed
        multiplied by the tax rate.

        When the entry has a payable or receivable account, the foreign debit and foreign credit
        will be the sum of the foreign credit or the foreign credit of all the other entries
        (line_ids) of the move (if the line has debit it will be the sum of the foreign credits,
        if it has credit it will be the sum of the foreign debits).

        If none of this is true and the currency of the journal entry is the same as the foreign
        currency of the company, the currency amount will be the one used to set the foreign debit
        or foreign credit on the corresponding line.

        And if there are two lines and one of them is in foreign currency, the amount placed in
        amount in currency will be placed in both corresponding lines in foreign debit and credit.

        If all the lines are made in the alternate currency, it will take the amount in amount in
        currency

        If the adjustment is placed, it overwrites both lines so that they are the same amount

        Ohterwise, if the move is not an invoice the foreign debit and foreign credit will be the
        debit and credit of the line multiplied by the inverse rate.

        In any case, if the foreign debit or foreign credit adjustments are set, the foreign debit
        and foreign credit will be the foreign debit or foreign credit adjustments.
        """
        self.ensure_one()
        subtotals_by_name = self.get_invoice_line_ids_subtotals_by_name()
        is_invoice = self.is_invoice(include_receipts=True)
        receivable_and_payable_account_types = {"asset_receivable", "liability_payable"}
        # self.line_ids.update({"foreign_debit": 0, "foreign_credit": 0})
        payment = self.payment_id

        # If the move is a retention payment we need to use the retention_foreign_amount of the
        # payment to compute the foreign debit/credit.
        if (
            payment
            and "retention_foreign_amount" in self.env["account.payment"]._fields
            and payment.is_retention
        ):
            for line in self.line_ids:
                line.update({"foreign_debit": 0, "foreign_credit": 0})
                if line.debit != 0:
                    line.foreign_debit = payment.retention_foreign_amount
                if line.credit != 0:
                    line.foreign_credit = payment.retention_foreign_amount
        else:
            line_foreign_currency_id = [
                line
                for line in self.line_ids
                if line.currency_id == self.env.company.currency_foreign_id
            ]

            for line in self.line_ids.sorted(lambda l: l.tax_ids, reverse=True):
                # If the line is an adjustment line, the foreign debit and foreign credit will be
                # the foreign debit and foreign credit adjustment fields.
                if line.not_foreign_recalculate:
                    continue

                line.update({"foreign_debit": 0, "foreign_credit": 0})

                # If the line is an adjustment line, the foreign debit and foreign credit will be
                # the foreign debit and foreign credit adjustment fields.
                if (
                    line.foreign_debit_adjustment + line.foreign_credit_adjustment
                ) != 0:
                    line.foreign_debit = abs(line.foreign_debit_adjustment)
                    line.foreign_credit = abs(line.foreign_credit_adjustment)
                    continue

                if (
                    len(self.line_ids) == 2
                    and len(line_foreign_currency_id) == 1
                    and line_foreign_currency_id[0].id != line.id
                ):
                    line_foreign_id = line_foreign_currency_id[0]
                    if (
                        line_foreign_id.foreign_debit_adjustment
                        + line_foreign_id.foreign_credit_adjustment
                    ) != 0:
                        line.foreign_debit = abs(line.foreign_debit_adjustment)
                        line.foreign_credit = abs(line.foreign_credit_adjustment)
                    else:
                        line.foreign_debit = (
                            abs(line_foreign_id.amount_currency)
                            if line_foreign_id.amount_currency < 0
                            else 0
                        )
                        line.foreign_credit = (
                            abs(line_foreign_id.amount_currency)
                            if line_foreign_id.amount_currency > 0
                            else 0
                        )
                    continue

                if (
                    len(line_foreign_currency_id) == len(self.line_ids)
                    and line.amount_currency != 0
                ):
                    if line.amount_currency > 0:
                        line.foreign_debit = abs(line.amount_currency)

                    if line.amount_currency < 0:
                        line.foreign_credit = abs(line.amount_currency)

                    continue

                line_name = line.name or False
                currency_id = self.env.company.currency_id
                subtotal_found = False
                if is_invoice and line_name in subtotals_by_name:
                    for subtotals in subtotals_by_name[line_name]:
                        if (
                            float_compare(
                                line.debit,
                                subtotals["price_subtotal"],
                                precision_digits=currency_id.decimal_places,
                            )
                            == 0
                        ):
                            line.foreign_debit = subtotals["foreign_subtotal"]
                            subtotal_found = True
                        if (
                            float_compare(
                                line.credit,
                                subtotals["price_subtotal"],
                                precision_digits=currency_id.decimal_places,
                            )
                            == 0
                        ):
                            line.foreign_credit = subtotals["foreign_subtotal"]
                            subtotal_found = True
                        if subtotal_found:
                            subtotals_by_name[line_name].remove(subtotals)
                            break
                    continue

                lines_with_same_tax = self.line_ids.filtered(
                    lambda l: l.tax_ids and l.tax_ids.name == line_name
                )

                if not (lines_with_same_tax and line_name):
                    line.foreign_debit = line.debit * self.foreign_inverse_rate
                    line.foreign_credit = line.credit * self.foreign_inverse_rate
                    continue

                def amount_by_line(lines, balance="debit"):
                    amount = 0
                    for line in lines:
                        balance_amount = line.foreign_debit
                        if balance == "credit":
                            balance_amount = line.foreign_credit
                        tax_amount = line.tax_ids._compute_amount(
                            float_round(
                                balance_amount,
                                precision_rounding=line.foreign_currency_id.rounding,
                            ),
                            balance_amount,
                        )
                        if (
                            self.env.company.tax_calculation_rounding_method
                            == "round_globally"
                        ):
                            amount += tax_amount
                        else:
                            amount += float_round(
                                tax_amount,
                                precision_rounding=line.foreign_currency_id.rounding,
                            )
                    return amount

                line.foreign_debit = amount_by_line(lines_with_same_tax, "debit")
                line.foreign_credit = amount_by_line(lines_with_same_tax, "credit")

        account_payable_or_receivable_line = self.line_ids.filtered(
            lambda l: l.account_id.account_type in receivable_and_payable_account_types
        )

        # We need to do this because the POS moves can have more than 1 journal entries with a
        # payable or receivable account, and in those cases is necessary that the foreign
        # debit/credit of that entry is computed using the rate, the same applies to the moves that
        # are not invoices.
        if (
            len(account_payable_or_receivable_line) > 1
            or (
                payment
                and "is_igtf_on_foreign_exchange" in self.env["account.payment"]._fields
                and payment.is_igtf_on_foreign_exchange
            )
            or not self.is_invoice(include_receipts=True)
        ):
            return

        if (
            account_payable_or_receivable_line.currency_id
            != self.env.company.currency_foreign_id
        ):
            if account_payable_or_receivable_line.debit > 0:
                account_payable_or_receivable_line.foreign_debit = sum(
                    self.line_ids.mapped("foreign_credit")
                )
            if account_payable_or_receivable_line.credit > 0:
                account_payable_or_receivable_line.foreign_credit = sum(
                    self.line_ids.mapped("foreign_debit")
                )

    def get_invoice_line_ids_subtotals_by_name(self):
        """
        This method is used to get the subtotal and foreign_subtotal of the invoice lines grouped
        by the lines names.

        It is meant to be used on the compute_line_ids_foreign_debit_and_credit method of this same
        model, and as there we use it to set the amounts of the foreign debit and foreign credit
        of the move lines and that values shoudn't be negative, we pass the absolute value of the
        subtotals.

        Returns
        -------
        type = defaultdict(list(dict))
            The subtotal and foreign subtotal of the invoice lines grouped by the lines names.
        """
        self.ensure_one()
        subtotals_by_name = defaultdict(list)
        for line in self.invoice_line_ids:
            subtotals_by_name[line.name].append(
                {
                    "price_subtotal": abs(line.price_subtotal),
                    "foreign_subtotal": abs(line.foreign_subtotal),
                }
            )
        return subtotals_by_name

    @api.depends("partner_id")
    def _compute_vat(self):
        """
        Compute the vat of the partner and add the prefix to it if it exists in the partner record
        """
        for move in self:
            if move.partner_id.prefix_vat and move.partner_id.vat:
                vat = str(move.partner_id.prefix_vat) + str(move.partner_id.vat)
            else:
                vat = str(move.partner_id.vat) if move.partner_id.vat else ''
            move.vat = vat.upper()

    @api.depends("invoice_date","foreign_currency_id","date")
    def _compute_rate(self):
        self._compute_rate_for_documents(
            self.filtered(lambda m: m.is_sale_document(include_receipts=True)),
            is_sale=True,
        )
        self._compute_rate_for_documents(
            self.filtered(lambda m: not m.is_sale_document(include_receipts=True)),
            is_sale=False,
        )

    @api.model
    def _compute_rate_for_documents(self, documents, is_sale):
        Rate = self.env["res.currency.rate"]

        for move in documents:
            if move.manually_set_rate:
                continue
            date_field = "invoice_date" if move.is_invoice(include_receipts=True) else "date"
            rate_date = getattr(move, date_field) or fields.Date.today()
            rate_values = Rate.compute_rate(move.foreign_currency_id.id, rate_date)
            move.write({
                'foreign_rate': rate_values.get("foreign_rate", 0),
                'foreign_inverse_rate': rate_values.get("foreign_inverse_rate", 0),
            })
            

    @api.depends("tax_totals")
    def _compute_foreign_taxable_income(self):
        """
        Compute the foreign taxable income of the invoice
        """
        for move in self:
            move.foreign_taxable_income = False
            if move.is_invoice() and move.invoice_line_ids and isinstance(move.tax_totals, dict):
                move.foreign_taxable_income = move.tax_totals.get("foreign_amount_untaxed", 0.0)

    @api.depends("tax_totals", "currency_id", "invoice_date", "amount_total")
    def _compute_foreign_total_billed(self):
        for move in self:
            move.foreign_total_billed = 0
            if not (
                move.invoice_line_ids
                and move.is_invoice(include_receipts=True)
                and move.tax_totals
            ):
                continue
            fc = move.company_id.currency_foreign_id
            if (
                move.currency_id
                and move.currency_id != move.company_id.currency_id
                and move.currency_id != fc
            ):
                move.foreign_total_billed = move.currency_id._convert(
                    move.amount_total,
                    fc,
                    move.company_id,
                    move.invoice_date or fields.Date.today(),
                )
            else:
                move.foreign_total_billed = move.tax_totals.get(
                    "foreign_amount_total", 0
                )



    @api.onchange("foreign_inverse_rate","invoice_date")
    def _onchange_foreign_inverse_rate(self):
        """
        Onchange the foreign rate and compute the foreign inverse rate
        """
        for rec in self:
            if rec.foreign_currency_id and rec.foreign_inverse_rate:
                if rec.foreign_inverse_rate < 0:
                    raise ValidationError(_("The rate entered cannot be negative."))
                elif rec.foreign_inverse_rate == 0:
                    raise ValidationError(_("The rate entered cannot be zero."))

    def _get_payments(self, line_ids):
        self.ensure_one()

        move_ids = line_ids.mapped("move_id.id")

        if not move_ids:
            return []

        payment_related = self.env["account.payment"].search(
            [("move_id", "in", move_ids)], order="id desc"
        )

        return payment_related

    def _get_account_move_line_related(self):
        self.ensure_one()

        account_move_line_ids = []

        reconciled_lines = self.line_ids._all_reconciled_lines()

        if not reconciled_lines:
            return account_move_line_ids

        account_move_line_ids = reconciled_lines.mapped("move_id.line_ids").ids

        return account_move_line_ids

    def _account_analytic_by_line_id(self, line_ids):
        self.ensure_one()

        account_analytic_by_line_id = {}

        for line_id in line_ids:
            if not line_id.analytic_distribution:
                account_analytic_by_line_id[line_id.id] = ""
                continue

            account_analytic_ids_ids = [
                int(analytic_id) for analytic_id in line_id.analytic_distribution.keys()
            ]
            account_analytic_ids = self.env["account.analytic.account"].browse(
                account_analytic_ids_ids
            )

            if not account_analytic_ids:
                account_analytic_by_line_id[line_id.id] = ""
                continue

            analytic_codes = []

            for code in account_analytic_ids.mapped("code"):
                if not code:
                    continue

                analytic_codes.append(code)

            account_analytic_by_line_id[line_id.id] = ", ".join(analytic_codes)

        return account_analytic_by_line_id

    # override
    def _get_retention_payment_move_ids(self, line_ids):
        return []

    def get_account_move_report_data(self):
        self.ensure_one()

        doc_title = ""
        doc_date = ""
        main_move_concept = self.ref
        main_move_payment_concept = ""
        payment_related_move_ids = []

        main_move = {
            "name": self.name,
        }

        line_ids_ids = self._get_account_move_line_related()
        line_ids = self.env["account.move.line"].browse(line_ids_ids)
        account_analytic_by_line_id = self._account_analytic_by_line_id(line_ids)

        payment_move_ids = self._get_payments(line_ids)
        retention_payment_move_ids = self._get_retention_payment_move_ids(line_ids)

        if payment_move_ids:
            first_payment = payment_move_ids[0]
            doc_date = first_payment.date

            main_move_payment_concept = first_payment.concept
            payment_related_move_ids = payment_move_ids.mapped("move_id.id")

            if self.amount_residual == 0:
                doc_title = first_payment.name

        # Used in the custom/l10n_ve_accountant/report/account_report.py
        data = {
            "doc_ids": line_ids_ids,
            "docs": line_ids,
            "doc_title": doc_title,
            "doc_date": doc_date,
            "main_move": self,
            "main_move_concept": main_move_concept,
            "main_move_payment_concept": main_move_payment_concept,
            "payment_related_move_ids": payment_related_move_ids,
            "retention_payment_move_ids": retention_payment_move_ids,
            "account_analytic_by_line_id": account_analytic_by_line_id,
            "group_analytic_accounting": self.env.user.has_group(
                "analytic.group_analytic_accounting"
            ),
        }

        return data

    def action_register_payment(self):
        if len(set(self.mapped("foreign_rate"))) > 1:
            raise UserError(
                _("You can only register payments for one foreign rate at a time.")
            )
        res = super().action_register_payment()
        res["context"]["default_foreign_rate"] = self[0].foreign_rate
        res["context"]["default_foreign_inverse_rate"] = self[0].foreign_inverse_rate
        return res

    def action_update_account_id(self):
        """
        Action to update account lines if product dont have account and category dont have account
        this method update account if change de journal_id.
        """
        for move in self:
            for line in move.line_ids:
                if line.tax_ids:
                    if (
                        not line.product_id.categ_id.property_account_income_categ_id
                        and not line.product_id.property_account_income_id
                    ):
                        line.account_id = move.journal_id.default_account_id

    def action_post(self):
        if not self.env.context.get("move_action_post_alert"):
            for move in self:
                if move.move_type in ("out_invoice", "out_refund"):
                    return {
                        'name': _('Alert'),
                        'type': 'ir.actions.act_window',
                        'res_model': 'move.action.post.alert.wizard',
                        'view_mode': 'form',
                        'view_id': False,
                        'target': 'new',
                        'context': {'default_move_id': self.id},
                    }

        for invoice in self:
            if (
                invoice.company_id.account_use_credit_limit
                and invoice.partner_id.use_partner_credit_limit
            ):
                total_pay = invoice.partner_id.credit + invoice.amount_residual
                if total_pay > invoice.partner_id.credit_limit:
                    decimal_places = invoice.currency_id.decimal_places
                    raise ValidationError(
                        _(
                            "No se ha confirmado la factura. Límite de crédito excedido. La cuenta por cobrar del cliente es de %s más %s en factura da un total de %s superando el límite de ventas de %s. Por favor cancele la factura o comuníquese con el administrador para aumentar el límite de crédito del cliente.",
                            round(invoice.partner_id.credit, decimal_places),
                            round(invoice.amount_residual, decimal_places),
                            round(total_pay, decimal_places),
                            round(invoice.partner_id.credit_limit, decimal_places),
                        )
                    )
        
            
        return super().action_post()

    @api.depends(
        "invoice_line_ids",
        "invoice_line_ids.price_subtotal",
        "foreign_inverse_rate",
        "foreign_currency_id",
        "foreign_rate",
    )
    def _compute_needed_terms(self):
        res = super()._compute_needed_terms()
        for invoice in self:
            if not isinstance(invoice.needed_terms, dict):
                continue
            if not invoice.is_invoice(include_receipts=True) or not invoice.invoice_line_ids:
                continue
            if not invoice.foreign_currency_id:
                continue
            rate_date = invoice.invoice_date or invoice.date or fields.Date.context_today(invoice)
            for key in invoice.needed_terms:
                balance = invoice.needed_terms[key].get('balance', 0)
                invoice.needed_terms[key]['foreign_balance'] = \
                    invoice.company_id.currency_id._convert(
                        balance, invoice.foreign_currency_id,
                        invoice.company_id, rate_date
                    )
        return res

    @api.constrains("invoice_line_ids")
    def _check_product_id(self):
        for moves in self:
            if moves.move_type == "entry":
                continue
            for line in moves.invoice_line_ids:
                if (
                    len(line.product_id) != 1
                    and line.display_type == "product"
                ):
                    raise ValidationError(_("All added lines must indicate the product."))
                

    # ── Sync dynamic lines: distribute foreign in PT ─────────────────────
    @contextmanager
    def _sync_dynamic_lines(self, container):
        with super()._sync_dynamic_lines(container):
            yield
            self._distribute_final_real_portion(container['records'])
        self._compute_foreign_tax_balance(container['records'])
        self._distribute_foreign_pt_residual(container['records'])

    def _compute_foreign_tax_balance(self, moves):
        """Compute and write foreign_balance on tax lines."""
        guarded = self.env.cr.cache.setdefault('_foreign_tax_balanced_set', set())
        for move in moves:
            if move.state != 'draft':
                continue
            if not move.is_invoice(include_receipts=True):
                continue
            fc = move.company_id.currency_foreign_id
            if not fc or not move.foreign_currency_id:
                continue

            fee = fc.round
            base_lines = move.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product'
            )
            if not base_lines:
                continue

            tax_amls = move.line_ids.filtered('tax_repartition_line_id')
            if not tax_amls:
                continue

            if move.id in guarded:
                continue
            guarded.add(move.id)
            try:
                foreign_key_to_amount = {}
                sign = move.direction_sign if move.is_invoice(include_receipts=True) else 1
                for bl in base_lines:
                    if bl.display_type != 'product':
                        continue
                    quantity = bl.quantity if move.is_invoice(include_receipts=True) else 1.0
                    discount = bl.discount if move.is_invoice(include_receipts=True) else 0.0
                    base_amount = sign * bl.foreign_price * (1 - discount / 100)
                    foreign_res = bl.tax_ids.compute_all(
                        base_amount,
                        currency=fc,
                        quantity=quantity,
                        product=bl.product_id,
                        partner=move.partner_id,
                        is_refund=move.move_type in ('out_refund', 'in_refund'),
                        handle_price_include=True,
                        include_caba_tags=move.always_tax_exigible,
                        fixed_multiplicator=sign,
                    )
                    for tax in foreign_res['taxes']:
                        if not tax['amount']:
                            continue
                        group_key = tax['tax_repartition_line_id']
                        foreign_key_to_amount[group_key] = foreign_key_to_amount.get(group_key, 0.0) + tax['amount']

                tax_lines_by_rep = {}
                for tl in tax_amls:
                    rep_line = tl.tax_repartition_line_id.id
                    tax_lines_by_rep.setdefault(rep_line, []).append(tl)

                for rep_line, lines in tax_lines_by_rep.items():
                    total_fb = foreign_key_to_amount.get(rep_line)
                    if total_fb is None:
                        continue
                    total_ac = sum(abs(l.amount_currency) for l in lines if l.amount_currency)
                    if fc.is_zero(total_ac):
                        continue
                    for tl in lines:
                        proportion = abs(tl.amount_currency) / total_ac
                        fb = fee(total_fb * proportion)
                        if not fc.is_zero(tl.foreign_balance - fb):
                            if fb >= 0:
                                tl.write({'foreign_debit': fb, 'foreign_credit': 0.0})
                            else:
                                tl.write({'foreign_debit': 0.0, 'foreign_credit': -fb})

                rate_date = move.invoice_date or move.date or fields.Date.context_today(move)
                if move.currency_id == fc:
                    expected = fee(abs(move.amount_total))
                else:
                    expected = fee(move.currency_id._convert(
                        abs(move.amount_total), fc, move.company_id, rate_date,
                        custom_rate=move.foreign_inverse_rate or 0.0,
                    ))
                product_total = sum(abs(l.foreign_subtotal) for l in move.line_ids if l.display_type == 'product')
                tax_total = sum(abs(l.foreign_balance) for l in move.line_ids if l.display_type == 'tax')
                diff = fee(expected - fee(product_total + tax_total))
                if not fc.is_zero(diff):
                    manual_alterno = any(move.invoice_line_ids.filtered('foreign_price_manual'))
                    counterpart = move.line_ids.filtered(
                        lambda l: not l.tax_repartition_line_id
                        and l.account_id.account_type in ('asset_receivable', 'liability_payable')
                        and not l.display_type
                    )
                    if counterpart:
                        target = counterpart[0]
                        side = 'foreign_debit' if target.foreign_debit > 0 else 'foreign_credit'
                        new_abs = fee(product_total + tax_total)
                        if manual_alterno:
                            _logger.info(
                                "Foreign tax reconciliation: move %s residual %s redirected "
                                "to counterpart (manual alterno present)",
                                move.id, diff,
                            )
                        target.write({
                            'foreign_debit': new_abs if side == 'foreign_debit' else 0.0,
                            'foreign_credit': new_abs if side == 'foreign_credit' else 0.0,
                            'not_foreign_recalculate': True,
                        })
            finally:
                guarded.discard(move.id)

    def _distribute_foreign_pt_residual(self, moves):
        """Distributes foreign_debit/foreign_credit across payment term lines
        proportionally to the native balance, forcing the total sum
        of foreign_debit = total sum of foreign_credit of the entry.

        Runs at the end of _sync_dynamic_lines (initial distribution)
        and also from the write hook of AccountMoveLine when the real
        portion adjusts the native balances of PT lines.
        """
        for move in moves:
            if move.state != 'draft':
                continue
            if not move.is_invoice(include_receipts=True):
                continue
            lines = move.line_ids
            pt_lines = lines.filtered(
                lambda l: l.display_type == "payment_term"
            )
            other = lines.filtered(
                lambda l: l.display_type not in ("payment_term", "cogs")
            )
            fc = move.company_id.currency_foreign_id
            if not fc:
                continue
            if not pt_lines:
                continue

            # For third currency use aggregate (total conversion),
            # for base/alternate currency use line-by-line sum
            if move.currency_id not in (move.company_id.currency_id, fc):
                aggregate = move.currency_id._convert(
                    abs(move.amount_total),
                    fc,
                    move.company_id,
                    move.invoice_date or fields.Date.today(),
                )
                total_debit = aggregate
                total_credit = aggregate
            else:
                total_debit = sum(other.mapped("foreign_debit"))
                total_credit = sum(other.mapped("foreign_credit"))

            sorted_pt = pt_lines.sorted(key=lambda l: l.id or 0)
            n = len(sorted_pt)
            total_balance = sum(abs(l.balance) for l in sorted_pt)

            for i, pt in enumerate(sorted_pt):
                is_credit_side = pt.credit > 0
                foreign_total = total_debit if is_credit_side else total_credit

                if n == 1:
                    my_foreign = foreign_total
                elif i < n - 1:
                    ratio = abs(pt.balance) / total_balance if total_balance else 0.0
                    my_foreign = fc.round(ratio * foreign_total)
                else:
                    assigned = sum(
                        fc.round(abs(l.balance) / total_balance * foreign_total)
                        if total_balance else 0.0
                        for l in list(sorted_pt)[:-1]
                    )
                    my_foreign = foreign_total - assigned

                new_fd = my_foreign if not is_credit_side else 0.0
                new_fc = my_foreign if is_credit_side else 0.0
                if not fc.is_zero(pt.foreign_debit - new_fd) or not fc.is_zero(pt.foreign_credit - new_fc):
                    pt.write({
                        'foreign_debit': new_fd,
                        'foreign_credit': new_fc,
                        'not_foreign_recalculate': True,
                    })

            # Adjust a non-PT line to absorb the rounding
            # difference between the aggregate and the line-by-line sum,
            # keeping the entry balanced to the correct value.
            if move.currency_id not in (move.company_id.currency_id, fc):
                side_total = sum(other.mapped("foreign_credit")) if move.is_inbound() else sum(other.mapped("foreign_debit"))
                diff = aggregate - side_total
                if not fc.is_zero(diff):
                    target_key = "foreign_credit" if move.is_inbound() else "foreign_debit"
                    target = other.filtered(lambda l: l[target_key] > 0).sorted(key=lambda l: -l[target_key])[:1]
                    if target:
                        target.write({
                            target_key: target[0][target_key] + diff,
                            'not_foreign_recalculate': True,
                        })

    # ── Real Portion ────────────────────────────────────────────

    def _distribute_final_real_portion(self, moves):
        distributes_keys = []
        try:
            for move in moves:
                if move.state != 'draft':
                    continue
                if move.currency_id == move.company_currency_id:
                    continue
                key = ('_real_portion_distributed', move.id)
                if self.env.cr.cache.get(key):
                    continue
                self.env.cr.cache[key] = True
                distributes_keys.append(key)
                cc = move.company_currency_id
                if move.is_invoice(include_receipts=True):
                    self._distribute_invoice_real_portion(move, cc)
                else:
                    self._distribute_entry_real_portion(move, cc)
        except Exception:
            for key in distributes_keys:
                self.env.cr.cache.pop(key,None)
            raise


    def _distribute_invoice_real_portion(self, move, cc):
        non_pt = move.line_ids.filtered(
            lambda l: l.display_type not in ('payment_term', 'cogs')
        )
        if not non_pt:
            return

        actual_non_pt = sum(non_pt.mapped('balance'))
        if cc.is_zero(actual_non_pt):
            return

        # Calculate expected total from direct document conversion
        total_currency = abs(move.amount_total)
        rate_date = move.invoice_date or move.date or fields.Date.context_today(move)
        expected_total = cc.round(move.currency_id._convert(
            total_currency, cc, move.company_id, rate_date,
            custom_rate=move.foreign_inverse_rate or 0.0,
        ))
        # non-PT lines are credit for sale docs (negative), debit for purchase docs (positive)
        sign = -1 if move.amount_total_signed > 0 else 1
        expected_total *= sign

        # Correct non_pt if it diverges from expected
        non_pt_diff = cc.round(expected_total - actual_non_pt)
        tolerance = cc.rounding * len(move.line_ids)
        if abs(non_pt_diff) > tolerance:
            _logger.warning(
                "Real portion: anomalous diff in move %s: diff=%s expected=%s actual=%s",
                move.id, non_pt_diff, expected_total, actual_non_pt,
            )
        if not cc.is_zero(non_pt_diff):
            self._distribute_to_lines(non_pt, non_pt_diff, cc)

        actual_non_pt = sum(non_pt.mapped('balance'))

        pt_lines = move.line_ids.filtered(
            lambda l: l.display_type == 'payment_term'
        )
        if pt_lines:
            target_pt = -actual_non_pt
            current_pt = sum(pt_lines.mapped('balance'))
            remaining = cc.round(target_pt - current_pt)
            if cc.is_zero(remaining):
                return
            self._distribute_to_lines(pt_lines, remaining, cc)
            move.real_portion_amount = cc.round(
                (move.real_portion_amount or 0.0) + remaining
            )
            move.real_portion_count += 1
        else:
            remaining = -actual_non_pt
            if cc.is_zero(remaining):
                return
            target_lines = move.line_ids.filtered(
                lambda l: not l.tax_repartition_line_id
            )
            self._distribute_to_lines(target_lines, remaining, cc)
            move.real_portion_amount = cc.round(
                (move.real_portion_amount or 0.0) + remaining
            )
            move.real_portion_count += 1

    def _distribute_entry_real_portion(self, move, cc):
        amount = cc.round(move.real_portion_amount or 0.0)
        if cc.is_zero(amount):
            return

        counterpart = move.line_ids.filtered(
            lambda l: not l.tax_repartition_line_id
            and l.account_id.account_type not in ('asset_cash', 'liability_credit_card')
        )
        if counterpart:
            self._distribute_to_lines(counterpart, amount, cc)
            move.real_portion_amount = cc.round(
                (move.real_portion_amount or 0.0) - amount
            )
            move.real_portion_count += 1


    @api.model
    def _distribute_to_lines(self, lines, amount, currency):
        if currency.is_zero(amount) or not lines:
            return

        sign = 1 if amount > 0 else -1
        abs_amount = abs(amount)
        bal_map = {line.id: line.balance for line in lines}
        total_abs = sum(abs(b) for b in bal_map.values())

        if currency.is_zero(total_abs):
            return

        sorted_ids = sorted(lines.ids, key=lambda lid: -abs(bal_map[lid]))
        remaining_units = round(abs_amount / currency.rounding)
        n = len(sorted_ids)

        for i, line_id in enumerate(sorted_ids):
            if remaining_units <= 0:
                break
            cur_bal = bal_map[line_id]
            if i < n - 1:
                ratio = abs(cur_bal) / total_abs
                share = currency.round(ratio * abs_amount)
                units = round(share / currency.rounding)
                if units > remaining_units:
                    units = remaining_units
            else:
                units = remaining_units
            new_balance = currency.round(cur_bal + sign * units * currency.rounding)
            lines.browse(line_id).balance = new_balance
            remaining_units -= units

    
