from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import index_exists, drop_index
from lxml import etree


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
        foreign_currency_symbol = ""
        foreign_currency_id = self.env.company.currency_foreign_id.id

        res = super().get_view(view_id, view_type, **options)

        if foreign_currency_id:
            foreign_currency_record = self.env["res.currency"].search(
                [("id", "=", int(foreign_currency_id))]
            )
            foreign_currency_symbol = foreign_currency_record.symbol
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

        If the move is an invoice or a receipt, the foreign debit and foreign credit will be
        the sum of the foreign_subtotal of the invoice lines when the line has the payable or
        receivable account of the partner and the sum of the price_subtotal of the invoice lines
        matches with either the debit or the credit of the line.

        Else, if the move is not an invoice or the line does not have the payable or receivable
        account of the partner, the foreign debit and foreign credit will be the debit and credit
        of the line multiplied by the inverse rate.
        """
        self.ensure_one()
        subtotals = self.get_invoice_line_ids_subtotals_sum()
        for line in self.line_ids:
            line_account_is_not_the_partner_receivable_or_payable = (
                line.account_id != self.partner_id.property_account_receivable_id
                and line.account_id != self.partner_id.property_account_payable_id
            )
            debit_or_credit_are_distinct_from_price_subtotal = (
                abs(line.debit) != subtotals[0] and abs(line.credit) != subtotals[0]
            )
            if (
                not self.is_invoice(include_receipts=True)
                or line_account_is_not_the_partner_receivable_or_payable
                or debit_or_credit_are_distinct_from_price_subtotal
            ):
                line.foreign_debit = line.debit * self.foreign_inverse_rate
                line.foreign_credit = line.credit * self.foreign_inverse_rate
                continue

            if abs(line.debit) > 0:
                line.foreign_debit = subtotals[1]
            if abs(line.credit) > 0:
                line.foreign_credit = subtotals[1]
        return

    def get_invoice_line_ids_subtotals_sum(self):
        """
        This method is used to get the subtotal and foreign_subtotal of the invoice lines.

        Returns
        -------
        type = tuple(float, float))
            The subtotal and foreign subtotal of the invoice lines
        """
        self.ensure_one()
        return (
            sum(line.price_subtotal for line in self.invoice_line_ids),
            sum(line.foreign_subtotal for line in self.invoice_line_ids),
        )

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
