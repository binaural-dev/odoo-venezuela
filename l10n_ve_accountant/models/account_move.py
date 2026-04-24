import logging
from collections import defaultdict

from lxml import etree
from contextlib import ExitStack, contextmanager
from odoo import _, api, fields, models,Command
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, index_exists
from odoo.tools.sql import drop_index
from odoo.tools.float_utils import float_round
from odoo.tools.misc import formatLang
from odoo.tools.misc import clean_context


_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"
    
    invoice_date_display = fields.Date(string="Invoice Date", default=fields.Date.today)

    @api.depends('invoice_date_display')
    def _compute_date(self):
        super()._compute_date()

    def _get_accounting_date_source(self):
        """
        Overrides the base method to substitute invoice_date with invoice_date_display
        as the primary source for determining the accounting date (date).
        This allows invoice_date to be used exclusively for exchange rate calculations.
        """
        self.ensure_one()
        return self.invoice_date_display or self.date

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

    company_currency_rate = fields.Float(
        string="Tasa de moneda de la compañía",
        compute="_compute_company_currency_rate",
        store=True,
        copy=False,
        help="Tasa de la moneda seleccionada en la compañía (campo inverse_rate_company de res.currency)",
    )

    @api.depends('currency_id')
    def _compute_company_currency_rate(self):
        for move in self:
            currency = move.currency_id
            currency_search = move.env["res.currency"].search([("id", "=", currency.id)], limit=1)
            if currency_search and hasattr(currency_search, "inverse_rate"):
                move.company_currency_rate = currency_search.inverse_rate or 1.0
            else:
                move.company_currency_rate = 1.0

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
        return self.env.company.foreign_currency_id.id or False

    foreign_currency_id = fields.Many2one(
        "res.currency",
        default=default_alternate_currency,
    )

    @api.onchange("move_type")
    def _onchange_move_type(self):
        self.invoice_date = False if self.move_type == "entry" else fields.Date.today()
        self.invoice_date_display = False if self.move_type == "entry" else fields.Date.today()

    def default_rate(self):
        """
        This method is used to get the rate of the payment.

        Returns
        -------
        type = float
            The rate of the payment
        """
        rate_values = self.env["res.currency.rate"].compute_rate(
            self.currency_id.id or self.env.ref("base.VEF").id,
            fields.Date.today(),
        )
        return rate_values.get("foreign_rate", 0)

    def default_rate(self):
        """
        This method is used to get the rate of the payment.

        Returns
        -------
        type = float
            The rate of the payment
        """
        rate_values = self.env["res.currency.rate"].compute_rate(
            self.currency_id.id or self.env.ref("base.VEF").id,
            fields.Date.today(),
        )
        return rate_values.get("foreign_rate", 0)

    foreign_rate = fields.Float(
        compute="_compute_rate",
        digits="Tasa",
        default=default_rate,
        store=True,
        tracking=True,
    )
    


    def default_inverse_rate(self):
        """
        This method is used to get the inverse rate of the payment.

        Returns
        -------
        type = float
            The inverse rate of the payment
        """
        rate_values = self.env["res.currency.rate"].compute_rate(
            self.currency_id.id or self.env.ref("base.VEF").id,
            fields.Date.today(),
        )
        return rate_values.get("foreign_inverse_rate", 0)
    
    foreign_inverse_rate = fields.Float(
        help="Rate that will be used as factor to multiply of the foreign currency for this move.",
        compute="_compute_rate",
        digits=(16, 15),
        default=default_inverse_rate,
        store=True,
        index=True,
    )


    move_currency_to_company_currency_rate = fields.Float(
        string="Move Currency to Company Currency Rate",
        compute="_compute_move_currency_to_company_currency_rate",
        copy=False,
        help="The conversion rate between the move currency and the company currency at the move date.",
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
    foreign_untaxed_total = fields.Monetary(string="foreign untaxed total", currency_field="foreign_currency_id", store=True, 
                                            compute='_compute_foreign_untaxed_total' )
    amount = fields.Float(tracking=True)

    amount_residual_company = fields.Monetary(
        string='residual amount',
        compute='_compute_amount',
        store=True,
        currency_field='company_currency_id'
    )

    @api.depends(
        'line_ids.matched_debit_ids.debit_move_id.move_id.origin_payment_id.is_matched',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.matched_credit_ids.credit_move_id.move_id.origin_payment_id.is_matched',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.balance',
        'line_ids.currency_id',
        'line_ids.amount_currency',
        'line_ids.amount_residual',
        'line_ids.amount_residual_currency',
        'line_ids.payment_id.state',
        'line_ids.full_reconcile_id',
        'state')
    def _compute_amount(self):
        super()._compute_amount()

        for move in self:
            total_residual_company = 0.0
            
            for line in move.line_ids:
                if line.display_type == 'payment_term':
                    total_residual_company += line.amount_residual
            sign = move.direction_sign
            #raise UserError(_("total_residual_company: %s") % total_residual_company)
            move.amount_residual_company = -sign * total_residual_company

    @api.onchange('invoice_date_display')
    def _onchange_invoice_date_display(self):
        for move in self:
            if move.invoice_date_display and move.is_sale_document(include_receipts=True):
                move.invoice_date = move.invoice_date_display


    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        context = self.with_context(active_test=False)
        return super(AccountMove, context).search_read(domain, fields, offset, limit, order)

    is_reset_to_draft_for_price_change = fields.Boolean(copy=False)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        context = self.with_context(active_test=False)
        return super(AccountMove, context).search_read(domain, fields, offset, limit, order)
    
    @api.depends('tax_totals')
    def _compute_foreign_untaxed_total(self):
        """
        Compute the foreign total untaxed of the invoice using the tax_totals
        """
        for move in self:
            move.foreign_untaxed_total = 0
            if not (
                move.invoice_line_ids
                and move.is_invoice(include_receipts=True)
                and move.tax_totals
            ):
                continue
            move.foreign_untaxed_total = move.tax_totals.get(
                "base_amount_foreign_currency", 0
            )
         
    @api.depends('currency_id', 'invoice_date')
    def _compute_move_currency_to_company_currency_rate(self):
        '''
        Compute the move currency to company currency rate'''
        for move in self:
            if move.currency_id == move.company_currency_id:
                move.move_currency_to_company_currency_rate = move.currency_id._get_conversion_rate(
                    from_currency=move.foreign_currency_id,
                    to_currency=move.company_currency_id,
                    company=move.company_id,
                    date=move._get_invoice_currency_rate_date(),
                )
            else:
                move.move_currency_to_company_currency_rate = move.currency_id._get_conversion_rate(
                    from_currency=move.currency_id,
                    to_currency=move.company_currency_id,
                    company=move.company_id,
                    date=move._get_invoice_currency_rate_date(),
                )

    @api.depends("line_ids.foreign_debit", "line_ids.foreign_credit")
    def _compute_total_debit_credit(self):
        for move in self:
            move.foreign_debit = sum(move.line_ids.mapped("foreign_debit"))
            move.foreign_credit = sum(move.line_ids.mapped("foreign_credit"))
            move.foreign_balance = move.foreign_debit - move.foreign_credit

    @api.depends("invoice_line_ids", "tax_totals")
    def _compute_detailed_amounts(self):
        for record in self:
            discount_amount = 0
            if not record.tax_totals:
                record.detailed_amounts = dict()
                return
            amount_taxed = record.tax_totals.get(
                "amount_total", 0
            ) - record.tax_totals.get("amount_untaxed", 0)
            total = 0

            for line in record.invoice_line_ids:
                subtotal = line.price_unit * line.quantity
                if line.discount > 0:
                    discount_amount += subtotal - line.price_subtotal
                total += subtotal

            record.detailed_amounts = dict(
                {
                    "gross_amount": total,
                    "formatted_gross_amount": formatLang(
                        self.env, total, currency_obj=self.currency_id
                    ),
                    "discount_amount": discount_amount,
                    "formatted_discount_amount": formatLang(
                        self.env, discount_amount, currency_obj=self.currency_id
                    ),
                    "gross_discount_amount": total,
                    "formatted_gross_discount_amount": formatLang(
                        self.env, total - discount_amount, currency_obj=self.currency_id
                    ),
                    "taxes_amount": amount_taxed,
                    "formatted_taxes_amount": formatLang(
                        self.env, amount_taxed, currency_obj=self.currency_id
                    ),
                }
            )

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
        foreign_currency_id = self.env.company.foreign_currency_id.id
        res = super().get_view(view_id, view_type, **options)

        if foreign_currency_id:
            foreign_currency_record = self.env["res.currency"].search(
                [("id", "=", int(foreign_currency_id))]
            )
            foreign_currency_symbol = foreign_currency_record.symbol or ""
            foreign_currency_name = foreign_currency_record.name or ""
            company_currency_symbol = self.env.company.currency_id.symbol or ""
            if view_type == "form":
                view_id = self.env.ref(
                    "l10n_ve_accountant.view_account_move_form_l10n_ve_accountant"
                ).id
                doc = etree.XML(res["arch"])
                page = doc.xpath("//page[@name='foreign_currency']")
                foreign_subtotal_line = doc.xpath("//page[@id='invoice_tab'][1]/field[1]/list[1]/field[@name='foreign_subtotal']")
                foreign_price_line = doc.xpath("//page[@id='invoice_tab'][1]/field[1]/list[1]/field[@name='foreign_price']")
                if foreign_subtotal_line:
                    foreign_subtotal_line[0].set("string", _("Subtotal") + " " + foreign_currency_name)
                if foreign_price_line:
                    foreign_price_line[0].set("string", _("Price") + " " + foreign_currency_name)
                if page:
                    page[0].set(
                        "string", _("Foreign Currency ") + " " + foreign_currency_symbol
                    )
                res["arch"] = etree.tostring(doc, encoding="unicode")

            if view_type == "list":
                view_id = self.env.ref(
                    "l10n_ve_accountant.l10n_ve_accountant_view_invoice_tree_inherit"
                ).id
                doc = etree.XML(res["arch"])
                foreign_total_billed_column = doc.xpath("//list/field[@name='foreign_total_billed']")
                foreign_untaxed_total_column = doc.xpath("//list/field[@name='foreign_untaxed_total']")
                amount_total_signed_column = doc.xpath("//list/field[@name='amount_total_signed']")
                amount_untaxed_signed_column = doc.xpath("//list/field[@name='amount_untaxed_signed']")
                if foreign_total_billed_column:
                    foreign_total_billed_column[0].set(
                        "string", _("Total") + " " + foreign_currency_name
                    )
                if foreign_untaxed_total_column:
                    foreign_untaxed_total_column[0].set(
                        "string", _("Untaxed Total") + " " + foreign_currency_name
                    )
                if amount_total_signed_column:
                    amount_total_signed_column[0].set(
                        "string", _("Total") + " " + company_currency_symbol
                    )
                if amount_untaxed_signed_column:
                    amount_untaxed_signed_column[0].set(
                        "string", _("Untaxed Total") + " " + company_currency_symbol
                    )
                
                res["arch"] = etree.tostring(doc, encoding="unicode")
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """
        Ensure that the foreign_rate and foreign_inverse_rate are computed and computes the foreign
        debit and foreign credit of the line_ids fields (journal entries) when the move is created.
        """
        moves = super().create(vals_list)

        for move in moves:
            if move.move_type != "in_invoice":
                move._compute_rate()
            if move.move_type in ["out_refund", "in_refund"] and move.reversed_entry_id:
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
        """
        computes the foreign debit and foreign credit of the line_ids fields (journal entries) when
        the move is edited.
        """
        # move_currency_to_company_currency_rate = vals.get('move_currency_to_company_currency_rate', False)
        # if move_currency_to_company_currency_rate:
        #     for move in self:
        #         vals.update({"last_foreign_rate": move.foreign_rate})
        #         vals.update({"foreign_rate": move_currency_to_company_currency_rate})
        #A REALIZAR PARA INTEGRA FLEXIBLE
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
        payment = self.origin_payment_id

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
                if line.currency_id == self.env.company.foreign_currency_id
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
                        tax_amount = line.tax_ids._get_tax_details(
                            line.price_unit,
                            line.quantity,
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
            != self.env.company.foreign_currency_id
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

    @api.depends("invoice_date")
    def _compute_rate(self):
        """
        Compute the rate of the invoice using the compute_rate method of the res.currency.rate model.
        """
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
        """
        Compute the rate for a set of documents (either sale invoices or purchase invoices/moves).
        """
        Rate = self.env["res.currency.rate"]

        for move in documents:
            if move.manually_set_rate:
                continue
            date_field = "invoice_date" if is_sale else "date"
            rate_date = getattr(move, date_field) or fields.Date.today()
            rate_values = Rate.compute_rate(move.foreign_currency_id.id, rate_date)
            move.foreign_rate = rate_values.get("foreign_rate", 0)
            move.foreign_inverse_rate = rate_values.get("foreign_inverse_rate", 0)

    @api.depends("tax_totals")
    def _compute_foreign_taxable_income(self):
        """
        Compute the foreign taxable income of the invoice
        """
        for move in self:
            move.foreign_taxable_income = False
            if move.is_invoice() and move.invoice_line_ids:
                move.foreign_taxable_income = move.tax_totals["base_amount_foreign_currency"]

    @api.depends("tax_totals")
    def _compute_foreign_total_billed(self):
        """
        Compute the foreign total billed of the invoice
        """
        for move in self:
            move.foreign_total_billed = 0
            if not (
                move.invoice_line_ids
                and move.is_invoice(include_receipts=True)
                and move.tax_totals
            ):
                continue
            move.foreign_total_billed = move.tax_totals.get("total_amount_foreign_currency",0)

    #override of base 
    @api.depends(
        'invoice_line_ids.currency_rate',
        'invoice_line_ids.tax_base_amount',
        'invoice_line_ids.tax_line_id',
        'invoice_line_ids.price_total',
        'invoice_line_ids.price_subtotal',
        'invoice_payment_term_id',
        'partner_id',
        'currency_id',
        'foreign_rate',
    )
    def _compute_tax_totals(self):
        # Adaptar el contexto para que el método de impuestos pueda recuperar el registro de factura
        for move in self:
            ctx = self.env.context.copy()
            ctx.update({'active_id': move.id, 'active_model': move._name})
            super(AccountMove, move.with_context(ctx))._compute_tax_totals()


    @api.onchange("foreign_rate")
    def _onchange_foreign_rate(self):
        """
        Onchange the foreign rate and compute the foreign inverse rate
        """
        if self.foreign_rate < 0 or self.foreign_inverse_rate < 0:
            raise ValidationError(_("The rate entered cannot be negative"))
        Rate = self.env["res.currency.rate"]
        for move in self:
            if not move.foreign_rate:
                return
            move.foreign_inverse_rate = Rate.compute_inverse_rate(move.foreign_rate)

    @api.onchange("foreign_inverse_rate")
    def _onchange_foreign_inverse_rate(self):
        """
        Onchange the foreign rate and compute the foreign inverse rate
        """
        if self.foreign_inverse_rate < 0:
            raise ValidationError(_("The rate entered cannot be negative."))
        elif self.foreign_inverse_rate == 0:
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

    #override 
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
        """
        Add the foreign rate and foreign inverse rate to the context of the action_register_payment.
        """
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
                        'context': {'default_move_id': move.id},
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
                invoice.needed_terms = {}
            is_draft = invoice.id != invoice._origin.id
            sign = 1 if invoice.is_inbound(include_receipts=True) else -1
            if invoice.is_invoice(True) and invoice.invoice_line_ids:
                invoice._compute_tax_totals()
                if invoice.invoice_payment_term_id:
                    if is_draft:
                        tax_amount_currency = 0.0
                        untaxed_amount_currency = 0.0
                        for line in invoice.invoice_line_ids:
                            untaxed_amount_currency += line.foreign_subtotal
                            tax_amount_currency += (
                                line.foreign_price_total - line.foreign_subtotal
                            )
                        untaxed_amount = untaxed_amount_currency
                        tax_amount = tax_amount_currency
                    else:
                        tax_amount = (
                            invoice.foreign_total_billed
                            - invoice.foreign_taxable_income
                        ) * sign
                        untaxed_amount = (invoice.foreign_taxable_income) * sign

                    invoice_payment_terms = (
                        invoice.invoice_payment_term_id._compute_terms(
                            date_ref=invoice.invoice_date_display
                            or invoice.date
                            or fields.Date.context_today(invoice),
                            currency=invoice.foreign_currency_id,
                            tax_amount_currency=tax_amount,
                            tax_amount=tax_amount,
                            untaxed_amount_currency=untaxed_amount,
                            untaxed_amount=untaxed_amount,
                            company=invoice.company_id,
                            sign=sign,
                        )
                    )

                    for term in invoice_payment_terms["line_ids"]:
                        if not isinstance(invoice.needed_terms, dict):
                            invoice.needed_terms = {}
                        for key in list(invoice.needed_terms.keys()):
                            if key["date_maturity"] == fields.Date.to_date(
                                term.get("date")
                            ):
                                invoice.needed_terms[key] = {
                                    **invoice.needed_terms[key],
                                    "foreign_balance": term["company_amount"],
                                }

                    # Fallback: if no term matched any needed_terms key (e.g. date_maturity
                    # mismatch due to immediate-payment terms with date_maturity=False),
                    # distribute foreign_balance across all keys proportionally.
                    if not isinstance(invoice.needed_terms, dict):
                        invoice.needed_terms = {}
                    unmatched_keys = [
                        key for key in invoice.needed_terms.keys()
                        if "foreign_balance" not in invoice.needed_terms[key]
                    ]
                    if unmatched_keys:
                        total_balance = sum(
                            abs(invoice.needed_terms[k].get("balance", 0))
                            for k in invoice.needed_terms.keys()
                        ) or 1
                        for key in unmatched_keys:
                            key_balance = abs(invoice.needed_terms[key].get("balance", 0))
                            proportion = key_balance / total_balance
                            invoice.needed_terms[key] = {
                                **invoice.needed_terms[key],
                                "foreign_balance": sign * invoice.foreign_total_billed * proportion,
                            }
                else:
                    if not isinstance(invoice.needed_terms, dict):
                        invoice.needed_terms = {}
                    for key in list(invoice.needed_terms.keys()):
                        invoice.needed_terms[key] = {
                            **invoice.needed_terms[key],
                            "foreign_balance": sign * invoice.foreign_total_billed,
                        }
        return res

    def button_draft(self):

        if self.move_type == "in_invoice":
            self.is_reset_to_draft_for_price_change = True

        return super().button_draft()

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
    #TODO:Funciones duplicadas de la logica de negocio de Odoo para el manejo de moneda foranea.
    #FUNCIONES FORANEAS
    def _get_rounded_foreign_base_and_tax_lines(self, round_from_tax_lines=True):
        """ Small helper to extract the base and tax lines for the taxes computation from the current move.
        This is a duplicate of Odoo's logic for handling foreign currency.

        The move could be stored or not and could have some features generating extra journal items acting as
        base lines for the taxes computation (e.g. epd, rounding lines).

        :param round_from_tax_lines:    Indicate if the manual tax amounts of tax journal items should be kept or not.
                                        It only works when the move is stored.
        :return:                        A tuple <base_lines, tax_lines> for the taxes computation.
        """
        self.ensure_one()
        AccountTax = self.env['account.tax']
        is_invoice = self.is_invoice(include_receipts=True)

        if self.id or not is_invoice:
            base_amls = self.line_ids.filtered(lambda line: line.display_type == 'product')
        else:
            base_amls = self.invoice_line_ids.filtered(lambda line: line.display_type == 'product')
        # Product type lines
        base_lines = [self._prepare_product_foreign_base_line_for_taxes_computation(line) for line in base_amls]
        tax_lines = []
        if self.id:
            # The move is stored so we can add the early payment discount lines directly to reduce the
            # tax amount without touching the untaxed amount.
            epd_amls = self.line_ids.filtered(lambda line: line.display_type == 'epd')

            # Discount type lines
            base_lines += [self._prepare_epd_foreign_base_line_for_taxes_computation(line) for line in epd_amls]
            cash_rounding_amls = self.line_ids \
                .filtered(lambda line: line.display_type == 'rounding' and not line.tax_repartition_line_id)
            # Rounding lines
            base_lines += [self._prepare_cash_rounding_foreign_base_line_for_taxes_computation(line) for line in cash_rounding_amls]
            AccountTax._add_tax_details_in_base_lines(base_lines, self.company_id)
            tax_amls = self.line_ids.filtered('tax_repartition_line_id')
            tax_lines = [self._prepare_tax_line_for_taxes_computation(tax_line) for tax_line in tax_amls]
            AccountTax._round_base_lines_tax_details(base_lines, self.company_id, tax_lines=tax_lines if round_from_tax_lines else [])
        else:
            # The move is not stored yet so the only thing we have is the invoice lines.
            base_lines += self._prepare_epd_base_lines_for_taxes_computation_from_base_lines(base_amls)
            AccountTax._add_tax_details_in_base_lines(base_lines, self.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, self.company_id)
        return base_lines, tax_lines

    def _prepare_product_foreign_base_line_for_taxes_computation(self, product_line):
        """ Convert an account.move.line having display_type='product' into a base line for the taxes computation.
        This is a duplicate of Odoo's logic for handling foreign currency.

        :param product_line: An account.move.line.
        :return: A base line returned by '_prepare_base_line_for_taxes_computation'.
        """
        self.ensure_one()
        is_invoice = self.is_invoice(include_receipts=True)
        sign = self.direction_sign if is_invoice else 1
        if is_invoice:
            rate = self.foreign_rate
        else:
            rate = (abs(product_line.amount_currency) / abs(product_line.balance)) if product_line.balance else 0.0

        return self.env['account.tax']._prepare_base_line_for_taxes_computation(
            product_line,
            price_unit=product_line.foreign_price,
            quantity=product_line.quantity if is_invoice else 1.0,
            discount=product_line.discount if is_invoice else 0.0,
            currency_id=product_line.foreign_currency_id,
            rate=rate,
            sign=sign,
            special_mode=False if is_invoice else 'total_excluded',
        )

    #TODO:FOREIGN
    def _prepare_epd_foreign_base_line_for_taxes_computation(self, epd_line):
        """ Convert an account.move.line having display_type='epd' into a base line for the taxes computation.
        This is a duplicate of Odoo's logic for handling foreign currency.

        :param epd_line: An account.move.line.
        :return: A base line returned by '_prepare_base_line_for_taxes_computation'.
        """
        self.ensure_one()
        sign = self.direction_sign
        rate = self.foreign_rate

        return self.env['account.tax']._prepare_base_line_for_taxes_computation(
            epd_line,
            price_unit=epd_line.foreign_price,
            quantity=1.0,
            sign=sign,
            special_mode='total_excluded',
            special_type='early_payment',
            currency_id=epd_line.foreign_currency_id,
            is_refund=self.move_type in ('out_refund', 'in_refund'),
            rate=rate,
        )
    #foreign function
    def _prepare_cash_rounding_foreign_base_line_for_taxes_computation(self, cash_rounding_line):
        """ Convert an account.move.line having display_type='rounding' into a base line for the taxes computation.
        This is a duplicate of Odoo's logic for handling foreign currency.

        :param cash_rounding_line: An account.move.line.
        :return: A base line returned by '_prepare_base_line_for_taxes_computation'.
        """
        self.ensure_one()
        sign = self.direction_sign
        rate = self.foreign_rate

        return self.env['account.tax']._prepare_base_line_for_taxes_computation(
            cash_rounding_line,
            price_unit=cash_rounding_line.foreign_price,
            quantity=1.0,
            sign=sign,
            special_mode='total_excluded',
            special_type='cash_rounding',
            currency_id=cash_rounding_line.foreign_currency_id,
            is_refund=self.move_type in ('out_refund', 'in_refund'),
            rate=rate,
        )
    #FIN DE FUNCIONES FORANEAS
# Unbalanced Lines Synchronization
    @contextmanager
    def _sync_tax_lines(self, container):
        AccountTax = self.env['account.tax']
        fake_base_line = AccountTax._prepare_base_line_for_taxes_computation(None)

        def get_base_lines(move):
            return move.line_ids.filtered(lambda line: line.display_type in ('product', 'epd', 'rounding', 'cogs'))

        def get_tax_lines(move):
            return move.line_ids.filtered('tax_repartition_line_id')

        def get_value(record, field):
            return self.env['account.move.line']._fields[field].convert_to_write(record[field], record)

        def get_tax_line_tracked_fields(line):
            return ('amount_currency', 'balance', 'analytic_distribution')

        def get_base_line_tracked_fields(line):
            grouping_key = AccountTax._prepare_base_line_grouping_key(fake_base_line)
            if line.move_id.is_invoice(include_receipts=True):
                extra_fields = ['price_unit', 'quantity', 'discount']
            else:
                extra_fields = ['amount_currency']
            return list(grouping_key.keys()) + extra_fields

        def field_has_changed(values, record, field):
            return get_value(record, field) != values.get(record, {}).get(field)

        def get_changed_lines(values, records, fields=None):
            return (
                record
                for record in records
                if record not in values
                or any(field_has_changed(values, record, field) for field in values[record] if not fields or field in fields)
            )

        def any_field_has_changed(values, records, fields=None):
            return any(record for record in get_changed_lines(values, records, fields))

        def is_write_needed(line, values):
            return any(
                self.env['account.move.line']._fields[fname].convert_to_write(line[fname], self) != values[fname]
                for fname in values
            )

        moves_values_before = {
            move: {
                field: get_value(move, field)
                for field in ('currency_id', 'partner_id', 'move_type')
            }
            for move in container['records']
            if move.state == 'draft'
        }
        base_lines_values_before = {
            move: {
                line: {
                    field: get_value(line, field)
                    for field in get_base_line_tracked_fields(line)
                }
                for line in get_base_lines(move)
            }
            for move in container['records']
        }
        tax_lines_values_before = {
            move: {
                line: {
                    field: get_value(line, field)
                    for field in get_tax_line_tracked_fields(line)
                }
                for line in get_tax_lines(move)
            }
            for move in container['records']
        }
        yield

        to_delete = []
        to_create = []
        for move in container['records']:
            if move.state != 'draft':
                continue

            tax_lines = get_tax_lines(move)
            base_lines = get_base_lines(move)
            move_tax_lines_values_before = tax_lines_values_before.get(move, {})
            move_base_lines_values_before = base_lines_values_before.get(move, {})
            if (
                move.is_invoice(include_receipts=True)
                and (
                    field_has_changed(moves_values_before, move, 'currency_id')
                    or field_has_changed(moves_values_before, move, 'move_type')
                )
            ):
                # Changing the type of an invoice using 'switch to refund' feature or just changing the currency.
                round_from_tax_lines = False
            elif changed_lines := list(get_changed_lines(move_base_lines_values_before, base_lines)):
                # A base line has been modified.
                round_from_tax_lines = (
                    # The changed lines don't affect the taxes.
                    all(
                        not line.tax_ids and not move_base_lines_values_before.get(line, {}).get('tax_ids')
                        for line in changed_lines
                    )
                    # Keep the tax lines amounts if an amount has been manually computed.
                    or (
                        list(move_tax_lines_values_before) != list(tax_lines)
                        or any(
                            self.env.is_protected(line._fields[fname], line)
                            for line in tax_lines
                            for fname in move_tax_lines_values_before[line]
                        )
                    )
                )

                # If the move has been created with all lines including the tax ones and the balance/amount_currency are provided on
                # base lines, we don't need to recompute anything.
                if (
                    round_from_tax_lines                             
                    and any(line[field] for line in changed_lines for field in ('amount_currency', 'balance'))
                ):
                    continue
            elif any_line := get_changed_lines(move_base_lines_values_before, base_lines, fields=['tax_ids']):
                any_line = any(any_line)
                round_from_tax_lines = any_field_has_changed(move_tax_lines_values_before, tax_lines)
            elif any(line not in base_lines for line, values in move_base_lines_values_before.items() if values['tax_ids']):
                # Removed a base line affecting the taxes.
                round_from_tax_lines = any_field_has_changed(move_tax_lines_values_before, tax_lines)
            else:
                continue

            base_lines_values, tax_lines_values = move._get_rounded_base_and_tax_lines(round_from_tax_lines=round_from_tax_lines)
            foreign_lines_values, foreign_tax_lines_values = move._get_rounded_foreign_base_and_tax_lines(round_from_tax_lines=False)
            AccountTax._add_accounting_data_in_base_lines_tax_details(base_lines_values, move.company_id, include_caba_tags=move.always_tax_exigible)
            AccountTax._add_accounting_data_in_base_lines_tax_details(foreign_lines_values, move.company_id, include_caba_tags=move.always_tax_exigible)
            tax_results = AccountTax._prepare_tax_lines(base_lines_values, move.company_id, tax_lines=tax_lines_values)
            foreign_tax_results = AccountTax._prepare_tax_lines(foreign_lines_values, move.company_id, tax_lines=foreign_tax_lines_values)
            for base_line, to_update in tax_results['base_lines_to_update']:
                line = base_line['record']
                foreign_base_update = None
                for f_base_line, f_to_update in foreign_tax_results.get('base_lines_to_update', []):
                    if f_base_line['record'].id == line.id:
                        foreign_base_update = f_to_update
                        break
                if foreign_base_update:
                    to_update['foreign_balance'] = foreign_base_update.get('amount_currency', 0)
                else:
                    # Fallback: convert company currency balance to foreign currency.
                    # Use invoice_date for invoices, date for journal entries.
                    rate_date = move.invoice_date if move.is_invoice(include_receipts=True) else move.date
                    to_update['foreign_balance'] = move.company_id.currency_id._convert(
                        to_update.get('balance', 0),
                        move.foreign_currency_id,
                        move.company_id,
                        rate_date or fields.Date.context_today(move),
                    )
                if is_write_needed(line, to_update):
                    line.write(to_update)
                else:
                    foreign_balance_new = to_update.get('foreign_balance')
                    if foreign_balance_new is not None and getattr(line, 'foreign_balance', None) != foreign_balance_new:
                        line.write({'foreign_balance': foreign_balance_new})
            for tax_line_vals in tax_results['tax_lines_to_delete']:
                to_delete.append(tax_line_vals['record'].id)

            for tax_line_vals in tax_results['tax_lines_to_add']:
                # Default: convert company currency balance to foreign currency via _convert.
                # Use invoice_date for invoices, date for journal entries.
                rate_date = move.invoice_date if move.is_invoice(include_receipts=True) else move.date
                foreign_balance = move.company_id.currency_id._convert(
                    tax_line_vals.get('balance', 0),
                    move.foreign_currency_id,
                    move.company_id,
                    rate_date or fields.Date.context_today(move),
                )
                for f_tax_line_vals in foreign_tax_results.get('tax_lines_to_add', []):
                    if (
                        f_tax_line_vals.get('tax_repartition_line_id') == tax_line_vals.get('tax_repartition_line_id') and
                        f_tax_line_vals.get('account_id')  == tax_line_vals.get('account_id')
                    ):
                        foreign_balance = f_tax_line_vals.get('amount_currency', foreign_balance)
                        break
                to_create.append({
                    **tax_line_vals,
                    'display_type': 'tax',
                    'move_id': move.id, 
                    'foreign_balance': foreign_balance,
                })

            for tax_line_vals, grouping_key, to_update in tax_results['tax_lines_to_update']:
                line = tax_line_vals['record']
                foreign_tax_update = None
                for f_tax_line_vals, f_grouping_key, f_to_update in foreign_tax_results.get('tax_lines_to_update', []):
                    if f_tax_line_vals['record'].id == line.id:
                        foreign_tax_update = f_to_update
                        break

                if not foreign_tax_update:
                    for f_tax_line_vals in foreign_tax_results.get('tax_lines_to_add', []):
                        if (
                            f_tax_line_vals.get('tax_repartition_line_id') == tax_line_vals.get('tax_repartition_line_id').id and
                            f_tax_line_vals.get('account_id') == tax_line_vals.get('account_id').id
                        ):
                            foreign_tax_update = f_tax_line_vals
                            break

                if foreign_tax_update:
                    to_update['foreign_balance'] = foreign_tax_update.get('amount_currency', 0)
                else:
                    # Fallback: convert company currency balance to foreign currency via _convert.
                    # Using amount_currency is wrong for company-currency invoices because
                    # amount_currency is in VEF, not in the foreign currency (USD).
                    # Use invoice_date for invoices, date for journal entries.
                    rate_date = move.invoice_date if move.is_invoice(include_receipts=True) else move.date
                    to_update['foreign_balance'] = move.company_id.currency_id._convert(
                        to_update.get('balance', 0),
                        move.foreign_currency_id,
                        move.company_id,
                        rate_date or fields.Date.context_today(move),
                    )
                if is_write_needed(line, to_update):
                    line.write(to_update)
                else:
                    # Si solo foreign_balance cambió, igual lo escribimos
                    foreign_balance_new = to_update.get('foreign_balance')
                    if foreign_balance_new is not None and getattr(line, 'foreign_balance', None) != foreign_balance_new:
                        line.write({'foreign_balance': foreign_balance_new})

        if to_delete:
            self.env['account.move.line'].browse(to_delete).with_context(dynamic_unlink=True).unlink()
        if to_create:
            self.env['account.move.line'].create(to_create)