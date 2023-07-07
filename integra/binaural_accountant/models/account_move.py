from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import index_exists, drop_index
from lxml import etree
from collections import defaultdict


class AccountMove(models.Model):
    _inherit = "account.move"

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

    invoice_date = fields.Date(default=fields.Date.today)

    foreign_rate = fields.Float(
        compute="_compute_rate",
        digits="Tasa",
        default=0.0,
        store=True,
        readonly=False,
    )
    foreign_inverse_rate = fields.Float(
        help="Rate that will be used as factor to multiply of the foreign currency for this move.",
        compute="_compute_rate",
        digits=(16, 15),
        default=0.0,
        store=True,
        readonly=False,
    )

    vat = fields.Char(
        string="VAT",
        help="VAT of the partner",
        compute="_compute_vat",
        readonly=False,
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
                    "binaural_accountant.view_account_move_form_binaural_invoice"
                ).id
                doc = etree.XML(res["arch"])
                page = doc.xpath("//page[@name='foreign_currency']")
                if page:
                    page[0].set("string", _("Foreign Currency ") + " " + foreign_currency_symbol)
                    res["arch"] = etree.tostring(doc, encoding="unicode")
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """
        Ensure that the foreign_rate and foreign_inverse_rate are computed and computes the foreign
        debit and foreign credit of the line_ids fields (journal entries) when the move is created.
        """
        moves = super().create(vals_list)
        moves._compute_rate()

        for move in moves:
            move.compute_line_ids_foreign_debit_and_credit()
        return moves

    def write(self, vals):
        """
        computes the foreign debit and foreign credit of the line_ids fields (journal entries) when
        the move is edited.
        """
        res = super().write(vals)
        for move in self:
            move.compute_line_ids_foreign_debit_and_credit()
        return res

    def compute_line_ids_foreign_debit_and_credit(self):
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

        Ohterwise, if the move is not an invoice the foreign debit and foreign credit will be the
        debit and credit of the line multiplied by the inverse rate.

        In any case, if the foreign debit or foreign credit adjustments are set, the foreign debit
        and foreign credit will be the foreign debit or foreign credit adjustments.
        """
        self.ensure_one()
        subtotals_by_name = self.get_invoice_line_ids_subtotals_by_name()
        is_invoice = self.is_invoice(include_receipts=True)
        receivable_and_payable_account_types = {"asset_receivable", "liability_payable"}
        for line in self.line_ids:
            # If the line is an adjustment line, the foreign debit and foreign credit will be the
            # foreign debit and foreign credit adjustment fields.
            if (line.foreign_debit_adjustment + line.foreign_credit_adjustment) != 0:
                line.foreign_debit = line.foreign_debit_adjustment
                line.foreign_credit = line.foreign_credit_adjustment
                continue
            line_name = line.name or False
            subtotal_found = False
            if is_invoice and line_name in subtotals_by_name:
                for subtotals in subtotals_by_name[line_name]:
                    if line.debit == subtotals[0]:
                        line.foreign_debit = subtotals[1]
                        subtotal_found = True
                    if line.credit == subtotals[0]:
                        line.foreign_credit = subtotals[1]
                        subtotal_found = True
                    if subtotal_found:
                        subtotals_by_name[line_name].remove(subtotals)
                        break
                continue

            lines_with_same_tax = self.line_ids.filtered(
                lambda l: l.tax_ids.description == line_name
            )
            if line.currency_id == self.env.company.currency_foreign_id:
                line.foreign_debit = line.amount_currency if line.debit > 0 else 0
                line.foreign_credit = line.amount_currency if line.credit > 0 else 0
                continue
            if not (lines_with_same_tax and line_name):
                line.foreign_debit = line.debit * self.foreign_inverse_rate
                line.foreign_credit = line.credit * self.foreign_inverse_rate
                continue
            line.foreign_debit = (
                sum(lines_with_same_tax.mapped("foreign_debit"))
                * lines_with_same_tax[0].tax_ids[0].amount
                / 100
            )
            line.foreign_credit = (
                sum(lines_with_same_tax.mapped("foreign_credit"))
                * lines_with_same_tax[0].tax_ids[0].amount
                / 100
            )

        account_payable_or_receivable_line = self.line_ids.filtered(
            lambda l: l.account_id.account_type in receivable_and_payable_account_types
        )

        if len(account_payable_or_receivable_line) > 0:
            return

        if account_payable_or_receivable_line.debit > 0:
            account_payable_or_receivable_line.foreign_debit = sum(
                self.line_ids.mapped("foreign_credit")
            )
        if account_payable_or_receivable_line.credit > 0:
            account_payable_or_receivable_line.foreign_credit = sum(
                self.line_ids.mapped("foreign_debit")
            )

    def _reverse_moves(self, default_values_list=None, cancel=False):
        """
        Ensure that the foreign debit and foreign credit of the line_ids fields (journal entries)
        are set to 0 when the move is reversed.

        This is done to avoid that the foreign debit and foreign credit of the journal entries of
        the reversed move are computed based on the foreign debit and foreign credit of the journal
        entries of the original move.
        """
        reverse_moves = super()._reverse_moves(default_values_list, cancel)
        reverse_moves.line_ids.write(
            {
                "foreign_debit": 0,
                "foreign_credit": 0,
                "foreign_debit_adjustment": 0,
                "foreign_credit_adjustment": 0,
            }
        )
        return reverse_moves

    def get_invoice_line_ids_subtotals_by_name(self):
        """
        This method is used to get the subtotal and foreign_subtotal of the invoice lines grouped
        by the lines names.

        Returns
        -------
        type = tuple(float, float))
            The subtotal and foreign subtotal of the invoice lines
        """
        self.ensure_one()
        subtotals_by_name = defaultdict(list)
        for line in self.invoice_line_ids:
            subtotals_by_name[line.name].append((line.price_subtotal, line.foreign_subtotal))
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
                vat = str(move.partner_id.vat)
            move.vat = vat.upper()

    @api.depends("invoice_date")
    def _compute_rate(self):
        """
        Compute the rate of the invoice using the compute_rate method of the res.currency.rate model.
        """
        Rate = self.env["res.currency.rate"]
        for move in self:
            rate_values = Rate.compute_rate(
                move.foreign_currency_id.id, move.invoice_date or fields.Date.today()
            )
            move.update(rate_values)

    @api.depends("tax_totals")
    def _compute_foreign_taxable_income(self):
        """
        Compute the foreign taxable income of the invoice
        """
        for move in self:
            move.foreign_taxable_income = False
            if move.is_invoice() and move.invoice_line_ids:
                move.foreign_taxable_income = move.tax_totals["foreign_amount_untaxed"]

    @api.depends("tax_totals")
    def _compute_foreign_total_billed(self):
        """
        Compute the foreign total billed of the invoice
        """
        for move in self:
            move.foreign_total_billed = 0
            if not (
                move.invoice_line_ids and move.is_invoice(include_receipts=True) and move.tax_totals
            ):
                continue
            move.foreign_total_billed = move.tax_totals["foreign_amount_total"]

    @api.depends(
        "invoice_line_ids.currency_rate",
        "invoice_line_ids.tax_base_amount",
        "invoice_line_ids.tax_line_id",
        "invoice_line_ids.price_total",
        "invoice_line_ids.price_subtotal",
        "invoice_payment_term_id",
        "partner_id",
        "currency_id",
        "foreign_rate",
    )
    def _compute_tax_totals(self):
        return super()._compute_tax_totals()

    @api.onchange("foreign_rate")
    def _onchange_foreign_rate(self):
        """
        Onchange the foreign rate and compute the foreign inverse rate
        """
        Rate = self.env["res.currency.rate"]
        for move in self:
            if not bool(move.foreign_rate):
                return
            move.foreign_inverse_rate = Rate.compute_inverse_rate(move.foreign_rate)

    def action_register_payment(self):
        """
        Add the foreign rate and foreign inverse rate to the context of the action_register_payment.
        """
        if len(set(self.mapped("foreign_rate"))) > 1:
            raise UserError(_("You can only register payments for one foreign rate at a time."))
        res = super().action_register_payment()
        res["context"]["default_foreign_rate"] = self[0].foreign_rate
        res["context"]["default_foreign_inverse_rate"] = self[0].foreign_inverse_rate
        return res
