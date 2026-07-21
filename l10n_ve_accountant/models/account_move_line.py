from contextlib import contextmanager
from odoo import api, fields, models, _
from odoo.tools import float_compare ,float_round, float_is_zero
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    not_foreign_recalculate = fields.Boolean()
    foreign_currency_id = fields.Many2one(
        related="move_id.foreign_currency_id", store=True
    )
    ves_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda VES",
        compute="_compute_ves_currency_id",
        store=True,
    )
    foreign_rate = fields.Float(related="move_id.foreign_rate", store=True)
    foreign_inverse_rate = fields.Float(
        related="move_id.foreign_inverse_rate", store=True, index=True
    )

    foreign_price = fields.Float(
        help="Foreign Price of the line",
        compute="_compute_foreign_price",
        digits="Foreign Product Price",
        store=True,
        readonly=False,
    )
    foreign_subtotal = fields.Monetary(
        help="Foreign Subtotal of the line",
        compute="_compute_foreign_subtotal",
        currency_field="foreign_currency_id",
        store=True,
    )
    foreign_price_total = fields.Monetary(
        help="Foreign Total of the line",
        compute="_compute_foreign_subtotal",
        currency_field="foreign_currency_id",
        store=True,
    )
    amount_currency = fields.Monetary(precompute=False)

    # Report fields
    foreign_debit = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_foreign_debit_credit",
        store=True,
    )
    foreign_credit = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_foreign_debit_credit",
        store=True,
    )
    foreign_balance = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_foreign_balance",
        inverse="_inverse_foreign_balance",
        store=True,
    )

    price_unit_ves = fields.Monetary(
        string="Unit Price VES",
        currency_field="ves_currency_id",
        help="Unit Price in VES currency",
        compute="_compute_price_unit_ves",
        store=True,
    )

    international_purchase_exent_product = fields.Boolean(string="International Purchase Exent Product")
    is_purchase_international = fields.Boolean(related="move_id.journal_id.is_purchase_international")

    @api.depends("price_unit", "foreign_inverse_rate", "move_id.currency_id")
    def _compute_price_unit_ves(self):
        for line in self:
            if line.currency_id and line.currency_id == line.company_id.currency_id:
                line.price_unit_ves = line.price_unit
            else:
                line.price_unit_ves = line.price_unit / line.currency_id.rate

    def _compute_ves_currency_id(self):
        ves_currency = self.env.ref("base.VES", raise_if_not_found=False) or self.env["res.currency"].search([("name", "=", "VES")], limit=1)
        for line in self:
            if line.currency_id and ves_currency and line.currency_id == ves_currency:
                line.ves_currency_id = ves_currency
            else:
                line.ves_currency_id = False

    foreign_debit_adjustment = fields.Monetary(
        currency_field="foreign_currency_id",
        help="When setted, this field will be used to fill the foreign debit field",
    )
    foreign_credit_adjustment = fields.Monetary(
        currency_field="foreign_currency_id",
        help="When setted, this field will be used to fill the foreign credit field",
    )

    config_deductible_tax = fields.Boolean(related='company_id.config_deductible_tax')

    not_deductible_tax = fields.Boolean(default=False)

    @api.depends('international_purchase_exent_product')
    def _compute_tax_ids(self):
        super()._compute_tax_ids()

    def _get_computed_taxes(self):
        res = super()._get_computed_taxes()
        if self.international_purchase_exent_product and self.company_id.exent_aliquot_purchase_international:
            res = self.company_id.exent_aliquot_purchase_international
        return res
    

    @api.depends("product_id", "move_id.name")
    def _compute_name(self):
        lines_without_name = self.filtered(lambda l: not l.name)
        res = super(AccountMoveLine, lines_without_name)._compute_name()
        for line in self.filtered(
            lambda l: l.move_type in ("out_invoice", "out_receipt")
            and l.account_id.account_type == "asset_receivable"
        ):
            line.name = line.move_id.name
        return res

    @api.depends("price_unit", "foreign_inverse_rate", "move_id.currency_id")
    def _compute_foreign_price(self):
        for line in self:
            company_currency = line.company_id.currency_id
            foreign_currency = line.company_id.foreign_currency_id
            if line.currency_id.id == company_currency.id:
                line.foreign_price = line.price_unit * line.foreign_inverse_rate
            elif line.currency_id.id == foreign_currency.id:
                line.foreign_price = line.price_unit
            else:
                line.foreign_price = line.currency_id._convert(
                    line.price_unit,
                    foreign_currency,
                    line.company_id,
                    line.move_id.invoice_date or fields.Date.today(),
                )

    @api.depends("foreign_price", "quantity", "discount", "tax_ids", "price_unit")
    def _compute_foreign_subtotal(self):
        for line in self:
            line_discount_price_unit = line.foreign_price * (
                1 - (line.discount / 100.0)
            )
            foreign_subtotal = line_discount_price_unit * line.quantity

            if line.tax_ids:
                taxes_res = line.tax_ids.compute_all(
                    line_discount_price_unit,
                    quantity=line.quantity,
                    currency=line.foreign_currency_id,
                    product=line.product_id,
                    partner=line.partner_id,
                    is_refund=line.is_refund,
                )
                line.foreign_subtotal = taxes_res["total_excluded"]
                line.foreign_price_total = taxes_res["total_included"]
            else:
                line.foreign_price_total = line.foreign_subtotal = foreign_subtotal

    # ── Helpers for foreign computation ──────────────────────────────

    def _set_foreign(self, value):
        """Set foreign_debit/credit from a signed value."""
        self.foreign_debit = abs(value) if value > 0 else 0.0
        self.foreign_credit = abs(value) if value < 0 else 0.0

    def _get_non_invoice_foreign_value(self):
        """Foreign value (signed) for non-invoice entries."""
        foreign_lines = self.move_id.line_ids.filtered(
            lambda l: l.currency_id == l.company_id.foreign_currency_id
        )
        currency_lines = self.move_id.line_ids.filtered(
            lambda l: l.currency_id == l.company_id.currency_id
        )
        balance = sum(foreign_lines.mapped("amount_currency"))
        if balance and len(currency_lines) == 1:
            return -balance

        # Third currency (neither base nor alternate)
        cur = self.currency_id
        if cur and cur != self.company_id.foreign_currency_id and cur != self.company_id.currency_id:
            return self.company_id.currency_id._convert(
                self.debit - self.credit,

                self.company_id.foreign_currency_id,
                self.company_id,
                self.date or fields.Date.context_today(self),
            )

        # Standard rate
        return (self.debit - self.credit) * self.foreign_inverse_rate

    def _get_foreign_value(self):
        """Return the foreign value (signed) for this line, or None."""
        self.ensure_one()

        # 1 — PT / Tax: use foreign_balance directly
        if self.display_type in ("payment_term", "tax"):
            return self.foreign_balance

        # 2 — Section / Note: zero
        if self.display_type in ("line_section", "line_note"):
            return 0.0

        # 3 — Manual debit adjustment
        if self.foreign_debit_adjustment:
            return abs(self.foreign_debit_adjustment)

        # 4 — Manual credit adjustment
        if self.foreign_credit_adjustment:
            return -abs(self.foreign_credit_adjustment)

        # 5 — Line already in alternate currency
        if self.currency_id == self.company_id.foreign_currency_id and self.amount_currency:
            return self.amount_currency


        # 7 — Non-invoice entry (journal entry, payment, etc.)
        if not self.move_id.is_invoice(include_receipts=True):
            return self._get_non_invoice_foreign_value()

        # 8 — Product / COGS: from foreign_subtotal
        # NOTE: foreign_subtotal uses native sign (positive = income)
        # while _set_foreign uses accounting sign (positive = debit).
        # Negate to align both conventions.
        if self.display_type in ("product", "cogs"):
            sign = self.move_id.direction_sign * -1
            return -(self.foreign_subtotal * sign)

        return None

    def _skip_foreign_compute(self):
        """Return True if this line should skip foreign computation."""
        return (
            self.move_id.journal_id == self.company_id.currency_exchange_journal_id
            or self.not_foreign_recalculate
        )

    @api.depends(
        "debit",
        "credit",
        "foreign_subtotal",
        "foreign_balance",
        "amount_currency",
        "not_foreign_recalculate",
        "foreign_debit_adjustment",
        "foreign_credit_adjustment",
        "foreign_inverse_rate",
    )
    def _compute_foreign_debit_credit(self):
        for line in self:
            if line._skip_foreign_compute():
                continue
            value = line._get_foreign_value()
            if value is not None:
                line._set_foreign(value)

    @api.depends("foreign_credit", "foreign_debit")
    def _compute_foreign_balance(self):
        for line in self:
            line.foreign_balance = line.foreign_debit - line.foreign_credit

    def _inverse_foreign_balance(self):
        for line in self:
            line.foreign_debit = (
                abs(line.foreign_balance) if line.foreign_balance > 0 else 0.0
            )
            line.foreign_credit = (
                abs(line.foreign_balance) if line.foreign_balance < 0 else 0.0
            )


    def _prepare_analytic_distribution_line(
        self, distribution, account_id, distribution_on_each_plan
    ):
        """
        This method adds the foreign_amount in the foreign currency to the analytical account line
        """
        self.ensure_one()
        res = super()._prepare_analytic_distribution_line(
            distribution, account_id, distribution_on_each_plan
        )
        account_id = int(account_id)
        account = self.env["account.analytic.account"].browse(account_id)
        distribution_plan = (
            distribution_on_each_plan.get(account.root_plan_id, 0) + distribution
        )
        decimal_precision = self.env["decimal.precision"].precision_get(
            "Percentage Analytic"
        )
        if (
            float_compare(distribution_plan, 100, precision_digits=decimal_precision)
            == 0
        ):
            foreign_amount = (
                -self.foreign_balance
                * (100 - distribution_on_each_plan.get(account.root_plan_id, 0))
                / 100.0
            )
        else:
            foreign_amount = -self.foreign_balance * distribution / 100.0

        res["foreign_amount"] = foreign_amount
        return res

    @api.model
    def abs_amount_lines_ids_adjust(self):
        for line in self:
            line.write(
                {
                    "foreign_debit_adjustment": abs(line.foreign_debit_adjustment),
                    "foreign_credit_adjustment": abs(line.foreign_credit_adjustment),
                    "foreign_debit": abs(line.foreign_debit),
                    "foreign_credit": abs(line.foreign_credit),
                }
            )

    @api.onchange("quantity")
    def _onchange_quantity(self):
        if self.quantity < 0:
            raise ValidationError(_("The quantity entered cannot be negative"))

    @api.onchange("price_unit")
    def _onchange_price_unit(self):
        if self.price_unit < 0:
            raise ValidationError(_("The price entered cannot be negative"))

    # ── Real Portion ──

    @contextmanager
    def _sync_invoice(self, container):
        if container['records'].env.context.get('skip_invoice_line_sync'):
            yield
            return

        with super()._sync_invoice(container):
            yield

        self._apply_product_real_portion(container['records'])

    @api.onchange('amount_currency', 'currency_id')
    def _inverse_amount_currency(self):
        """
        Updates the 'balance' (company currency amount) whenever the 'amount_currency' 
        or 'currency_id' changes, ensuring a symmetric rounding.

        This method addresses the common floating-point discrepancy where a balance 
        converted to foreign currency and then back to company currency results in 
        a small difference (e.g., 0.01). 

        The logic performs a "Symmetry Test":
        1. It calculates the initial balance using the current exchange rate.
        2. It simulates a back-conversion to the foreign currency.
        3. If the back-conversion doesn't match the original 'amount_currency' due to 
        rounding noise, it applies a micro-adjustment to the 'balance' in the 
        company currency (VES) to force a perfect match.

        :return: None
        """
        for line in self:
            if line.currency_id == line.company_id.currency_id and line.balance != line.amount_currency:
                line.balance = line.amount_currency
                
            elif (
                line.currency_id != line.company_id.currency_id
                and not line.move_id.is_invoice(True)
                and not self.env.is_protected(self._fields['balance'], line)
            ):
                rate = line.currency_rate
                if not rate:
                    continue
                    
                raw_balance = line.amount_currency / rate
                
                rounded_balance = line.company_id.currency_id.round(raw_balance)
                
                back_to_foreign = rounded_balance * rate
                diff_foreign = line.amount_currency - back_to_foreign
                
                if not float_is_zero(diff_foreign, precision_rounding=line.currency_id.rounding):
                    adjustment = float_round(diff_foreign / rate, precision_rounding=line.company_id.currency_id.rounding)
                    line.balance = rounded_balance + adjustment
                else:
                    line.balance = rounded_balance

    @api.model
    def _apply_product_real_portion(self, lines):
        """Correct cross-currency rounding on product lines.

        When an invoice is in a foreign currency, each product line's balance
        (company currency) is independently rounded to the company currency's
        precision. The sum of these rounded balances can differ by the currency
        rounding unit from the rounded conversion of the total line amount at
        the raw exchange rate. This method distributes that difference across
        product lines proportionally so the entry remains balanced.

        The expected total is computed via ``_convert`` (the raw rate from
        ``res.currency.rate``), not from ``line.currency_rate`` (which is
        derived from an already-rounded balance and amplifies the error).
        """
        for move in lines.move_id:
            if not move.is_invoice(include_receipts=True):
                continue
            if move.currency_id == move.company_currency_id:
                continue
            if move.state != 'draft':
                continue
            if move.env.cr.cache.get(('_real_portion_distributed', move.id)):
                continue

            cc = move.company_currency_id
            product_lines = lines.filtered(
                lambda l: l.move_id == move
                and l.display_type == 'product'
                and l.currency_id != l.company_currency_id
            )
            if not product_lines:
                continue

            total_currency = sum(product_lines.mapped('amount_currency'))
            rate_date = move.invoice_date or move.date or fields.Date.context_today(move)
            expected = cc.round(move.currency_id._convert(
                total_currency, cc, move.company_id, rate_date
            ))
            actual = sum(product_lines.mapped('balance'))
            diff = cc.round(expected - actual)

            if cc.is_zero(diff):
                continue

            self._adjust_product_distribution(
                product_lines, diff, cc, move,
            )

    @api.model
    def _adjust_product_distribution(
        self, product_lines, diff, cc, move,
    ):
        bal_map = {line.id: line.balance for line in product_lines}
        total_abs = sum(abs(b) for b in bal_map.values())
        if cc.is_zero(total_abs):
            return

        sign = 1 if diff > 0 else -1
        abs_diff = abs(diff)
        sorted_ids = sorted(product_lines.ids, key=lambda lid: -abs(bal_map[lid]))
        remaining_units = round(abs_diff / cc.rounding)
        n = len(sorted_ids)

        for i, line_id in enumerate(sorted_ids):
            if remaining_units <= 0:
                break
            cur_bal = bal_map[line_id]
            if i < n - 1:
                ratio = abs(cur_bal) / total_abs
                share = cc.round(ratio * abs_diff)
                units = round(share / cc.rounding)
                if units > remaining_units:
                    units = remaining_units
            else:
                units = remaining_units
            new_balance = cc.round(cur_bal + sign * units * cc.rounding)
            product_lines.browse(line_id).balance = new_balance
            remaining_units -= units

        move.real_portion_count += 1

    