from contextlib import contextmanager
from odoo import api, fields, models, Command, _
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

    def _get_foreign_rate_date(self):
        """Fecha con la que se busca la tasa para convertir montos de esta linea.

        Unica fuente de fecha para todo calculo de moneda alterna de la linea:
        _compute_foreign_price, _compute_price_unit_ves y
        _get_non_invoice_foreign_value.

        Facturas y notas de credito/debito: invoice_date, que en esta
        localizacion es la fecha de la tasa (la fecha visible del documento es
        invoice_date_display). Asientos manuales y de pago: la fecha contable
        (date), que es la unica que tienen.
        """
        self.ensure_one()
        move = self.move_id
        if move.is_invoice(include_receipts=True):
            return move.invoice_date or move.date or fields.Date.context_today(self)
        return move.date or fields.Date.context_today(self)

    @api.depends(
        "price_unit",
        "currency_id",
        "move_id.currency_id",
        "move_id.invoice_date",
        "move_id.date",
    )
    def _compute_price_unit_ves(self):
        for line in self:
            company_currency = line.company_id.currency_id
            if not line.currency_id or line.currency_id == company_currency:
                line.price_unit_ves = line.price_unit
                continue
            # Convertir con _convert() y no dividiendo entre currency_id.rate:
            # no revienta si la tasa del dia no esta cargada (rate = 0).
            # round=False + redondeo a la precision del campo (igual que
            # _compute_foreign_price): _convert() redondea por defecto a los
            # decimales de la moneda destino (VEF = 2), pero "Product Price"
            # tiene mas digitos (6) - sin round=False esa precision extra se
            # pierde antes de que el float_round de abajo pueda hacer nada.
            precision = self.env["decimal.precision"].precision_get(
                "Product Price"
            )
            line.price_unit_ves = float_round(
                line.currency_id._convert(
                    line.price_unit,
                    company_currency,
                    line.company_id,
                    line._get_foreign_rate_date(),
                    round=False,
                ),
                precision_digits=precision
            )

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

    @api.depends(
        "price_unit",
        "currency_id",
        "move_id.currency_id",
        "move_id.invoice_date",
        "move_id.date",
    )
    def _compute_foreign_price(self):
        for line in self:
            foreign_currency = line.company_id.foreign_currency_id
            if not foreign_currency:
                line.foreign_price = 0.0
            elif line.currency_id.id == foreign_currency.id:
                line.foreign_price = line.price_unit
            else:
                # round=False + redondeo a la precision del campo: _convert()
                # redondea por defecto a los decimales de la moneda destino
                # (USD = 2), pero foreign_price usa "Foreign Product Price"
                # cuya precision es configurable. Sin esto, un precio
                # unitario pequeño se pierde al
                # convertir y foreign_subtotal (= foreign_price x cantidad)
                # arrastra el error multiplicado por la cantidad.
                precision = self.env["decimal.precision"].precision_get(
                    "Foreign Product Price"
                )
                line.foreign_price = float_round(
                    line.currency_id._convert(
                        line.price_unit,
                        foreign_currency,
                        line.company_id,
                        line._get_foreign_rate_date(),
                        round=False,
                    ),
                    precision_digits=precision,
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

        return self.company_id.currency_id._convert(
            self.debit - self.credit,
            self.company_id.foreign_currency_id,
            self.company_id,
            self._get_foreign_rate_date(),
        )

    def _get_foreign_value(self):
        """Return the foreign value (signed) for this line, or None."""
        self.ensure_one()

        # 1 — PT / Tax: use foreign_balance directly. `_sync_tax_lines`
        # (account_move.py, `_round_mode`) ahora resincroniza y escribe
        # `foreign_balance` de la linea de impuesto directamente cuando
        # cambia `move_currency_to_company_currency_rate` -- esa escritura
        # dispara `_inverse_foreign_balance`, que fija foreign_debit/credit.
        # Ya no hace falta re-derivar el valor aca con `_convert()`.
        if self.display_type in ("payment_term", "tax"):
            return self.foreign_balance

        # 2 — Section / Subsection / Note: zero. `line_subsection` is the
        # display_type Odoo 19 added to this family; without it a
        # subsection fell through to the branches below and could be
        # handed a non-zero alternate-currency balance, unbalancing the
        # entry in the foreign currency.
        if self.display_type in ("line_section", "line_subsection", "line_note"):
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
        "move_id.invoice_date",
        "move_id.date",
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

    
    @api.constrains("discount")
    def _check_max_discount(self):
        """Validates that discount value on invoice lines does not reach or exceed 100%."""
        for line in self:
            if not line.product_id:
                continue

            if line.discount >= 100.0:
                product_name = line.product_id.display_name
                discount_val = f"{line.discount}%"

                raise UserError(
                    _(
                        "Product: %(product)s\n"
                        "Discount: %(discount)s\n"
                        "Discounts of 100%% or higher are not allowed on invoices.\n"
                        "Please adjust the discount percentage before saving."
                    )
                    % {
                        "product": product_name,
                        "discount": discount_val,
                    }
                )

    def _check_constrains_account_id_journal_id(self):
        for line in self.filtered(
            lambda x: x.display_type not in ('line_section', 'line_subsection', 'line_note')
        ):
            journal = line.move_id.journal_id
            journal_currency = journal.currency_id
            # If the journal has no currency of its own, it accepts entries in
            # any currency (core behavior). If it DOES force a currency, no
            # line may use a different one -- block before running the core's
            # own validations (archived account, account secondary currency).
            if journal_currency and line.currency_id != journal_currency:
                raise UserError(_(
                    'The journal %(journal)s only accepts entries in %(journal_currency)s, '
                    'but this line is in %(line_currency)s.',
                    journal=journal.name,
                    journal_currency=journal_currency.name,
                    line_currency=line.currency_id.name,
                ))

    # ── Alternate-currency ("moneda alterna") exchange difference ──
    # Extends core's own exchange-difference move (or builds a standalone
    # one) so its lines also carry `foreign_debit`/`foreign_credit`.
    # Ver openspec: design-notes.md § _prepare_reconciliation_single_partial

    def _prepare_reconciliation_single_partial(self, debit_values, credit_values, shadowed_aml_values=None, **kwargs):
        debit_line = debit_values.get('aml')
        credit_line = credit_values.get('aml')
        initial_debit_residual = debit_values.get('amount_residual')
        initial_credit_residual = credit_values.get('amount_residual')

        res = super()._prepare_reconciliation_single_partial(
            debit_values, credit_values, shadowed_aml_values=shadowed_aml_values, **kwargs
        )

        # Honor core's own suppression context, or an absent
        # `exchange_values` here reads as "nothing to fix" and wrongly
        # falls through to the standalone branch below.
        # Ver openspec: design-notes.md § _prepare_reconciliation_single_partial
        if self.env.context.get('no_exchange_difference') or self.env.context.get('no_exchange_difference_no_recursive'):
            return res

        exchange_values = (res or {}).get('exchange_values') or {}
        line_commands = (exchange_values.get('move_values') or {}).get('line_ids') or []

        if not debit_line or not credit_line or not (res or {}).get('partial_values'):
            return res

        # Reuse core's own exchange-move date, or `max(debit, credit)` if
        # it built none -- never "today" (wrong rate for past partials).
        # Ver openspec: design-notes.md § _prepare_reconciliation_single_partial
        exchange_date = exchange_values.get('move_values', {}).get('date') or max(debit_line.date, credit_line.date)

        # Prefer the invoice side as rate source (core's own convention);
        # fall back to the earlier-dated side when neither is an invoice.
        # Ver openspec: design-notes.md § _prepare_reconciliation_single_partial
        if debit_line.move_id.is_invoice(True):
            rate_source, counterpart = debit_line, credit_line
        elif credit_line.move_id.is_invoice(True):
            rate_source, counterpart = credit_line, debit_line
        elif debit_line.date <= credit_line.date:
            rate_source, counterpart = debit_line, credit_line
        else:
            rate_source, counterpart = credit_line, debit_line

        if line_commands:
            # Core already decided a company-currency fix is needed --
            # reuse ITS OWN computed amount per pair, never re-derived.
            # Ver openspec: design-notes.md § _prepare_reconciliation_single_partial
            self._inject_foreign_exchange_amounts(exchange_values, rate_source, debit_line, credit_line)
            return res

        # Empty `line_commands` genuinely means nothing needed fixing in
        # company currency at all (core zeroes residuals before any other
        # module diverts the document) -- safe to diff residuals directly.
        # Ver openspec: design-notes.md § _prepare_reconciliation_single_partial
        settled = self._get_settled_company_amount(
            debit_line, debit_values.get('amount_residual'), initial_debit_residual,
        )
        if not settled:
            return res

        # No sign re-orientation needed: the result is symmetric in
        # debit/credit, already correctly signed for `rate_source` as-is.
        # Ver openspec: design-notes.md § compute_alt_exchange_diff_from_settlement
        alt_diff = debit_line._compute_alt_exchange_diff_from_settlement(
            credit_line,
            initial_debit_residual, debit_values.get('amount_residual'),
            initial_credit_residual, credit_values.get('amount_residual'),
            rate_source,
        )
        if not alt_diff:
            return res

        self._queue_standalone_foreign_exchange_difference(rate_source, counterpart, alt_diff, exchange_date)
        return res

    def _get_settled_company_amount(self, debit_line, new_residual, initial_residual):
        """Signed company-currency amount settled in this partial, from the
        DEBIT side's perspective. Only meaningful when core found no
        per-side currency asymmetry to fix (see caller).
        """
        company_currency = debit_line.company_id.currency_id
        consumed = company_currency.round(abs(initial_residual or 0.0) - abs(new_residual or 0.0))
        if company_currency.is_zero(consumed):
            return 0.0
        sign = 1.0 if (initial_residual or 0.0) >= 0 else -1.0
        return sign * consumed

    def _foreign_exposure_at_residual(self, residual):
        """Pure function of `residual`: alternate-currency amount out of
        this line's own FIXED `foreign_debit`/`foreign_credit`, scaled by
        `residual / original` (never re-derived from a rate here). Being
        pure is what makes multi-partial sums telescope with zero drift.
        Ver openspec: design-notes.md § foreign_exposure_at_residual
        """
        self.ensure_one()
        company_currency = self.company_id.currency_id
        original = self.debit - self.credit
        if company_currency.is_zero(original) or company_currency.is_zero(residual):
            return 0.0
        original_foreign = self.foreign_debit - self.foreign_credit
        if company_currency.is_zero(residual - original):
            return original_foreign
        foreign_currency = self.company_id.foreign_currency_id
        return foreign_currency.round(original_foreign * (residual / original))

    def _alt_exchange_diff_currency(self, rate_source):
        """The company's alternate currency, or `False` if the toggle is
        off, none is configured, or `rate_source` is itself denominated
        directly in it (its exposure is already fixed -- nothing to revalue).
        Ver openspec: design-notes.md § Exclusión: factura en moneda alterna
        """
        company = self.company_id
        if not company.l10n_ve_use_foreign_exchange_diff:
            return False
        foreign_currency = company.foreign_currency_id
        if not foreign_currency or foreign_currency == company.currency_id:
            return False
        if rate_source.currency_id == foreign_currency:
            return False
        return foreign_currency

    def _compute_alt_exchange_diff_from_settlement(
        self, other, self_residual_before, self_residual_after,
        other_residual_before, other_residual_after, rate_source,
    ):
        """Signed alt-currency diff from settling `self` and `other` in one
        partial: `consumed(self) + consumed(other)`, each from that line's
        OWN fixed foreign amount. Symmetric by construction, so no sign
        re-orientation is ever needed by the caller.
        Ver openspec: design-notes.md § compute_alt_exchange_diff_from_settlement
        """
        self.ensure_one()
        foreign_currency = self._alt_exchange_diff_currency(rate_source)
        if not foreign_currency:
            return 0.0
        consumed_self = (
            self._foreign_exposure_at_residual(self_residual_before)
            - self._foreign_exposure_at_residual(self_residual_after)
        )
        consumed_other = (
            other._foreign_exposure_at_residual(other_residual_before)
            - other._foreign_exposure_at_residual(other_residual_after)
        )
        diff = foreign_currency.round(consumed_self + consumed_other)
        return 0.0 if foreign_currency.is_zero(diff) else diff

    def _compute_alt_exchange_diff_from_slice(self, residual_before, rate_source):
        """One-sided version of `_compute_alt_exchange_diff_from_settlement`,
        for a slice of THIS line's residual that core already isolated as
        "the leftover this line needs fixed" (`_inject_foreign_exchange_amounts`).
        Ver openspec: design-notes.md § compute_alt_exchange_diff_from_slice
        """
        self.ensure_one()
        foreign_currency = self._alt_exchange_diff_currency(rate_source)
        if not foreign_currency:
            return 0.0
        diff = foreign_currency.round(self._foreign_exposure_at_residual(residual_before))
        return 0.0 if foreign_currency.is_zero(diff) else diff

    def _resolve_closing_line(self, closing_vals, debit_line, credit_line):
        """Identify which of `debit_line`/`credit_line` a `closing_vals`
        dict (from core) belongs to, via its `reconciled_lines_ids`
        command -- more robust than assuming a fixed pairing order.
        Ver openspec: design-notes.md § resolve_closing_line
        """
        for command in closing_vals.get('reconciled_lines_ids') or []:
            if isinstance(command, (list, tuple)) and len(command) == 3 and command[0] == 6:
                closed_ids = set(command[2] or [])
                if debit_line.id in closed_ids:
                    return debit_line
                if credit_line.id in closed_ids:
                    return credit_line
        return None

    def _inject_foreign_exchange_amounts(self, exchange_values, rate_source, debit_line, credit_line):
        """Adds `foreign_debit`/`foreign_credit` to the lines core just
        built, deriving the base amount from what core itself put in each
        pair's `debit`/`credit` (never re-derived independently).
        Ver openspec: design-notes.md § inject_foreign_exchange_amounts
        """
        line_commands = (exchange_values.get('move_values') or {}).get('line_ids') or []
        i = 0
        while i + 1 < len(line_commands):
            closing_vals = line_commands[i][2]
            gain_vals = line_commands[i + 1][2]
            # Reconstructs core's signed `amount_residual`; falls back to
            # `amount_currency` for core's second branch
            # (`amount_residual_currency`, `debit`/`credit` both 0 there).
            # Ver openspec: design-notes.md § inject_foreign_exchange_amounts
            base_amount = closing_vals.get('credit', 0.0) - closing_vals.get('debit', 0.0)
            if not base_amount:
                base_amount = -closing_vals.get('amount_currency', 0.0)
            owning_line = self._resolve_closing_line(closing_vals, debit_line, credit_line) or rate_source
            alt_diff = owning_line._compute_alt_exchange_diff_from_slice(base_amount, rate_source)
            if alt_diff:
                closing_vals['foreign_debit'] = abs(alt_diff) if alt_diff < 0.0 else 0.0
                closing_vals['foreign_credit'] = abs(alt_diff) if alt_diff > 0.0 else 0.0
                closing_vals['not_foreign_recalculate'] = True
                gain_vals['foreign_debit'] = abs(alt_diff) if alt_diff > 0.0 else 0.0
                gain_vals['foreign_credit'] = abs(alt_diff) if alt_diff < 0.0 else 0.0
                gain_vals['not_foreign_recalculate'] = True
                exchange_values['move_values']['l10n_ve_exchange_foreign_diff_entry'] = True
            i += 2

    def _queue_standalone_foreign_exchange_difference(self, line, counterpart, amount_foreign, exchange_date):
        """Queues a standalone, alternate-only exchange difference entry
        on the cursor, flushed once by `_create_exchange_difference_moves`
        (the `account.partial.reconcile` for these lines doesn't exist yet
        at this point in core's flow). `amount_foreign` is already signed.
        """
        if not amount_foreign:
            return
        exchange_date = exchange_date or fields.Date.context_today(self)
        queue = getattr(self.env.cr, '_l10n_ve_foreign_exchange_pending', None)
        if queue is None:
            queue = []
            self.env.cr._l10n_ve_foreign_exchange_pending = queue
        queue.append({
            'line': line, 'counterpart': counterpart,
            'amount_foreign': amount_foreign, 'date': exchange_date,
        })

    @api.model
    def _create_exchange_difference_moves(self, exchange_diff_values_list):
        """Runs `super()` first (native entries, already carrying injected
        alternate amounts), then flushes the standalone-entry queue.
        """
        exchange_moves = super()._create_exchange_difference_moves(exchange_diff_values_list)

        # Popped BEFORE processing (plain cursor state, not ORM-
        # transactional): must not survive a savepoint rollback into the
        # next attempt on the same cursor. Same pattern as
        # `l10n_ve_exchange_difference._create_exchange_difference_moves`.
        pending = getattr(self.env.cr, '_l10n_ve_foreign_exchange_pending', None) or []
        self.env.cr._l10n_ve_foreign_exchange_pending = []
        try:
            for descriptor in pending:
                descriptor['line']._create_standalone_foreign_exchange_difference_entry(
                    descriptor['counterpart'], descriptor['amount_foreign'], descriptor['date'],
                )
        finally:
            self.env.cr._l10n_ve_foreign_exchange_pending = []

        return exchange_moves

    def _find_settlement_partial(self, counterpart):
        """The exact `account.partial.reconcile` these two LINES (not just
        moves, to stay precise across several installments) became, once
        core has created it -- available by the time this runs.
        """
        self.ensure_one()
        return self.env['account.partial.reconcile'].search([
            ('debit_move_id', 'in', (self.id, counterpart.id)),
            ('credit_move_id', 'in', (self.id, counterpart.id)),
        ], order='id desc', limit=1)

    def _create_standalone_foreign_exchange_difference_entry(self, counterpart, amount_foreign, entry_date):
        """Posts core's same two-line exchange-difference shape (same
        accounts/journal) with zero company-currency amounts and only
        `foreign_debit`/`foreign_credit` set. Idempotency and reversal ride
        on the NATIVE `exchange_move_id` field (reused if already set on
        this partial; core reverses it automatically on unlink).
        """
        self.ensure_one()
        company = self.company_id
        payment_move = counterpart.move_id if counterpart else self.env['account.move']
        partial = self._find_settlement_partial(counterpart)

        if partial and partial.exchange_move_id:
            return partial.exchange_move_id

        journal = self._get_exchange_journal(company)
        exchange_account = self._get_exchange_account(company, amount_foreign)
        if not journal or not exchange_account:
            raise UserError(_(
                "Configure the 'Exchange Gain or Loss Journal' and its "
                "Gain/Loss accounts in your company settings before "
                "reconciling documents with the alternate currency "
                "exchange difference enabled."
            ))

        move = self.env['account.move'].with_company(company).with_context(no_exchange_difference=True).create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': entry_date,
            'l10n_ve_exchange_foreign_diff_entry': True,
            'l10n_ve_exchange_foreign_source_move_id': self.move_id.id,
            'l10n_ve_exchange_foreign_payment_move_id': payment_move.id,
            'line_ids': [
                Command.create({
                    'name': _('Alternate currency exchange difference'),
                    'account_id': self.account_id.id,
                    'currency_id': self.currency_id.id,
                    'partner_id': self.partner_id.id,
                    'debit': 0.0,
                    'credit': 0.0,
                    'not_foreign_recalculate': True,
                    'foreign_debit': abs(amount_foreign) if amount_foreign < 0.0 else 0.0,
                    'foreign_credit': abs(amount_foreign) if amount_foreign > 0.0 else 0.0,
                }),
                Command.create({
                    'name': _('Alternate currency exchange difference'),
                    'account_id': exchange_account.id,
                    'currency_id': self.currency_id.id,
                    'partner_id': self.partner_id.id,
                    'debit': 0.0,
                    'credit': 0.0,
                    'not_foreign_recalculate': True,
                    'foreign_debit': abs(amount_foreign) if amount_foreign > 0.0 else 0.0,
                    'foreign_credit': abs(amount_foreign) if amount_foreign < 0.0 else 0.0,
                }),
            ],
        })
        move.with_context(validate_analytic=False)._post(soft=False)

        if partial:
            # Claims this move as the partial's own exchange-diff move --
            # from here on, breaking this exact settlement (removing
            # `partial`) makes core reverse `move` automatically, the same
            # way it already does for its own native exchange entries.
            partial.exchange_move_id = move.id
        else:
            _logger.warning(
                "l10n_ve_use_foreign_exchange_diff: could not locate the "
                "settlement partial for move %s (source %s) -- entry %s "
                "was created but will NOT be reversed automatically if "
                "this reconciliation is later undone.",
                self.move_id.id, self.id, move.id,
            )
        return move

    # ── "Reconciled Items" must surface the standalone entry too ──
    # The standalone entry never reconciles by design, so core's own
    # `open_reconcile_view` never finds it on its own.
    # Ver openspec: design-notes.md § open_reconcile_view (Reconciled Items)

    def open_reconcile_view(self):
        action = super().open_reconcile_view()
        # Matched on either linked move; only the "closing" line (same
        # account type as the receivable/payable settled) belongs here.
        # Ver openspec: design-notes.md § open_reconcile_view (Reconciled Items)
        extra_lines = self.env['account.move.line'].search([
            '|',
            ('move_id.l10n_ve_exchange_foreign_source_move_id', 'in', self.move_id.ids),
            ('move_id.l10n_ve_exchange_foreign_payment_move_id', 'in', self.move_id.ids),
            ('account_id.account_type', 'in', ('asset_receivable', 'liability_payable')),
            ('parent_state', '=', 'posted'),
            # A reversed entry stays `posted` by design -- exclude it, the
            # settlement it was tracking is gone.
            ('move_id.reversal_move_ids', '=', False),
        ])
        if not extra_lines:
            return action

        # Parsed defensively: core builds a single `[('id', 'in', ids)]`
        # leaf today, but nothing guarantees that shape survives a patch.
        domain = action.get('domain')
        existing_ids = set()
        if isinstance(domain, (list, tuple)):
            for leaf in domain:
                if (
                    isinstance(leaf, (list, tuple)) and len(leaf) == 3
                    and leaf[0] == 'id' and leaf[1] == 'in'
                    and isinstance(leaf[2], (list, tuple, set))
                ):
                    existing_ids.update(leaf[2])

        action['domain'] = [('id', 'in', list(existing_ids | set(extra_lines.ids)))]
        return action
