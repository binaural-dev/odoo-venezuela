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
    # Extends core's OWN exchange-difference move (not a separate one) so
    # its two lines carry both the company-currency amount (untouched) and
    # `foreign_debit`/`foreign_credit`. If company currency needs no fix at
    # all, the same two-line shape is built standalone, alternate-only.
    # Hooked at `_prepare_reconciliation_single_partial` (runs every
    # partial, unlike `_prepare_exchange_difference_move_vals`).

    def _prepare_reconciliation_single_partial(self, debit_values, credit_values, shadowed_aml_values=None, **kwargs):
        debit_line = debit_values.get('aml')
        credit_line = credit_values.get('aml')
        initial_debit_residual = debit_values.get('amount_residual')
        initial_credit_residual = credit_values.get('amount_residual')

        res = super()._prepare_reconciliation_single_partial(
            debit_values, credit_values, shadowed_aml_values=shadowed_aml_values, **kwargs
        )

        # Core itself uses this context to suppress its OWN exchange-diff
        # logic (e.g. closing the diff entry's own receivable line, CABA
        # entries) -- honoring it the same way is required, otherwise an
        # absent `exchange_values` here (because core skipped it) reads as
        # "nothing to fix" and wrongly falls through to the standalone
        # branch below, creating an entry core deliberately did not want.
        if self.env.context.get('no_exchange_difference') or self.env.context.get('no_exchange_difference_no_recursive'):
            return res

        exchange_values = (res or {}).get('exchange_values') or {}
        line_commands = (exchange_values.get('move_values') or {}).get('line_ids') or []

        if not debit_line or not credit_line or not (res or {}).get('partial_values'):
            return res

        # When core built its own exchange move, reuse its EXACT date
        # (`max(debit_aml.date, credit_aml.date)`, same convention core
        # itself uses). When it didn't (standalone branch), that date was
        # never computed at all -- falling back to "today" here would
        # silently use TODAY's rate instead of THIS partial's actual
        # settlement date, corrupting every installment except one that
        # happens to be reconciled on the same day the test/process runs.
        exchange_date = exchange_values.get('move_values', {}).get('date') or max(debit_line.date, credit_line.date)

        # Prefer the invoice side as "the document" whose booking rate
        # matters -- same preference `account.partial.reconcile._compute_company_id`
        # already uses ("exchange diff entries should be created on the
        # invoice side if any"). Needed even in the injection branch below:
        # core is free to pick EITHER side (often the payment's own
        # internal 'entry' move) as the one it fixes, and that side's own
        # `foreign_inverse_rate` reflects ITS OWN date (the payment/
        # settlement date), not the original booking rate -- comparing a
        # line against its own rate always yields zero.
        if debit_line.move_id.is_invoice(True):
            rate_source, counterpart = debit_line, credit_line
        elif credit_line.move_id.is_invoice(True):
            rate_source, counterpart = credit_line, debit_line
        elif debit_line.date <= credit_line.date:
            # Neither is a real invoice (misc entries, both sides
            # 'entry') -- prefer the EARLIER-dated line: it is the one
            # whose booking rate can actually differ from the settlement
            # rate. Preferring an arbitrary side (e.g. always debit) risks
            # picking the line dated AT settlement, whose own rate always
            # equals the current one, silently zeroing the diff.
            rate_source, counterpart = debit_line, credit_line
        else:
            rate_source, counterpart = credit_line, debit_line

        if line_commands:
            # Core itself decided a company-currency fix is needed for at
            # least one of these two lines -- reuse ITS OWN computed
            # amount per pair (never re-derive it independently: a plain
            # before/after residual comparison is nonzero for BOTH sides
            # of any ordinary settlement, not just the side that actually
            # needs a currency correction, and would misattribute an
            # alt-diff to the wrong/unaffected side).
            self._inject_foreign_exchange_amounts(exchange_values, exchange_date, rate_source)
            return res

        # `line_commands` empty means no OTHER module intercepted core's
        # generic entry either (e.g. `l10n_ve_exchange_difference` diverting
        # it into a fiscal Note) -- if one had, `debit_values`/`credit_values`
        # `amount_residual` would already read as closed regardless (core
        # zeroes out `remaining_debit/credit_amount` itself, BEFORE handing
        # off to whichever module ends up building the actual document --
        # verified against core `account/models/account_move_line.py`,
        # `_prepare_reconciliation_single_partial`). So an empty
        # `line_commands` here genuinely means "nothing needed fixing in
        # company currency at all", not just "core didn't build one".
        # Safe to derive the settled amount from a before/after residual
        # comparison: with no fix of any kind involved, both sides settle
        # the exact same principal, so there's no per-side asymmetry to
        # misattribute.
        settled = self._get_settled_company_amount(
            debit_line, debit_values.get('amount_residual'), initial_debit_residual,
        )
        if not settled:
            return res
        # Re-orient the sign to `rate_source`'s own side: `settled` above
        # is signed from the debit side's perspective.
        if rate_source is credit_line:
            settled = -settled

        self._queue_standalone_foreign_exchange_difference(rate_source, counterpart, settled, exchange_date)
        return res

    def _get_settled_company_amount(self, debit_line, new_residual, initial_residual):
        """Signed company-currency amount settled in this partial, from the
        DEBIT side's perspective, same sign convention as `amount_residual`.
        Only meaningful when core found no per-side currency asymmetry to
        fix (see caller).
        """
        company_currency = debit_line.company_id.currency_id
        consumed = company_currency.round(abs(initial_residual or 0.0) - abs(new_residual or 0.0))
        if company_currency.is_zero(consumed):
            return 0.0
        sign = 1.0 if (initial_residual or 0.0) >= 0 else -1.0
        return sign * consumed

    def _compute_foreign_exchange_amount(self, base_amount, exchange_date):
        """Alternate-currency amount for `base_amount` (company currency),
        re-priced at `exchange_date` vs. the document's own booking rate.
        Returns 0.0 if disabled, misconfigured, or no rate to compare.
        """
        self.ensure_one()
        company = self.company_id
        if not company.l10n_ve_use_foreign_exchange_diff:
            return 0.0
        foreign_currency = company.foreign_currency_id
        if not foreign_currency or foreign_currency == company.currency_id:
            return 0.0
        if company.currency_id.is_zero(base_amount):
            return 0.0
        # `self` (rate_source) is the invoice-side line. When the invoice
        # itself is denominated IN the alternate currency, its exposure in
        # that currency is already fixed and exact (`amount_currency`) --
        # there is nothing left to revalue, regardless of any native
        # company-currency diff (that diff is purely an artifact of
        # measuring value in a currency that moved, not a real change in
        # the USD-denominated debt). Re-pricing it via the company-currency
        # rate delta here would inject a fictitious alternate-currency
        # difference and unbalance the alternate-currency total.
        if self.currency_id == foreign_currency:
            return 0.0
        original_inverse_rate = self.move_id.foreign_inverse_rate
        if not original_inverse_rate:
            return 0.0
        # `with_company(company)` -- `compute_rate` (`l10n_ve_rate`) filters
        # by `self.env.company` internally; without this, a caller whose
        # active company differs from `company` (multi-company cron, a
        # user in another branch) would read the wrong company's rate,
        # possibly with the currency/inverse convention flipped.
        rate_values = self.env['res.currency.rate'].with_company(company).compute_rate(
            foreign_currency.id, exchange_date or fields.Date.context_today(self)
        )
        current_inverse_rate = rate_values.get('foreign_inverse_rate')
        if not current_inverse_rate:
            _logger.warning(
                "l10n_ve_use_foreign_exchange_diff: no exchange rate for %s at %s "
                "(move %s) -- alternate-currency exchange difference skipped.",
                foreign_currency.name, exchange_date, self.move_id.id,
            )
            return 0.0
        # `foreign_inverse_rate` is alt-per-company-unit (e.g. USD per VES).
        # If it DROPS (VES weakens), the alt-currency value of `base_amount`
        # fell -- a loss, which must be POSITIVE (same sign convention as
        # `amount_residual`: positive = loss). Hence (original - current),
        # not (current - original).
        diff_foreign = foreign_currency.round(base_amount * (original_inverse_rate - current_inverse_rate))
        return 0.0 if foreign_currency.is_zero(diff_foreign) else diff_foreign

    def _inject_foreign_exchange_amounts(self, exchange_values, exchange_date, rate_source):
        """Adds `foreign_debit`/`foreign_credit` to the lines core just
        built in `exchange_values['move_values']['line_ids']`, deriving
        the base amount directly from what core itself put in each pair's
        `debit`/`credit` (never re-derived independently -- see the
        caller for why that would misattribute the wrong side). The
        booking rate always comes from `rate_source` (the invoice side of
        THIS partial), never from whichever line core happens to close --
        core may pick the payment's own internal entry, whose own rate is
        dated at settlement, making a self-comparison always zero.
        """
        line_commands = (exchange_values.get('move_values') or {}).get('line_ids') or []
        i = 0
        while i + 1 < len(line_commands):
            closing_vals = line_commands[i][2]
            gain_vals = line_commands[i + 1][2]
            # Reconstructs core's own signed `amount_residual` from the
            # exact `debit`/`credit` it computed for the closing line
            # (`'debit': -residual if residual<0 else 0, 'credit':
            # residual if residual>0 else 0` -- see core's
            # `_prepare_exchange_difference_move_vals`). Core has a SECOND
            # branch (`recon_currency == company_currency`) where the fix
            # is expressed via `amount_residual_currency` instead --
            # `debit`/`credit` are both 0 there and the amount lives in
            # `amount_currency` (`-amount_residual_currency`) -- fall back
            # to that so this branch isn't silently skipped.
            base_amount = closing_vals.get('credit', 0.0) - closing_vals.get('debit', 0.0)
            if not base_amount:
                base_amount = -closing_vals.get('amount_currency', 0.0)
            alt_diff = rate_source._compute_foreign_exchange_amount(base_amount, exchange_date)
            if alt_diff:
                closing_vals['foreign_debit'] = abs(alt_diff) if alt_diff < 0.0 else 0.0
                closing_vals['foreign_credit'] = abs(alt_diff) if alt_diff > 0.0 else 0.0
                closing_vals['not_foreign_recalculate'] = True
                gain_vals['foreign_debit'] = abs(alt_diff) if alt_diff > 0.0 else 0.0
                gain_vals['foreign_credit'] = abs(alt_diff) if alt_diff < 0.0 else 0.0
                gain_vals['not_foreign_recalculate'] = True
                exchange_values['move_values']['l10n_ve_exchange_foreign_diff_entry'] = True
            i += 2

    def _queue_standalone_foreign_exchange_difference(self, line, counterpart, base_amount, exchange_date):
        """Queues a standalone, alternate-only exchange difference entry
        for `line`/`counterpart` on the cursor, flushed once by
        `_create_exchange_difference_moves` below (the exact
        `account.partial.reconcile` these two lines become doesn't exist
        yet at this point in core's flow -- it's located later, once it
        does, by `_create_standalone_foreign_exchange_difference_entry`).
        """
        exchange_date = exchange_date or fields.Date.context_today(self)
        alt_diff = line._compute_foreign_exchange_amount(base_amount, exchange_date)
        if not alt_diff:
            return
        queue = getattr(self.env.cr, '_l10n_ve_foreign_exchange_pending', None)
        if queue is None:
            queue = []
            self.env.cr._l10n_ve_foreign_exchange_pending = queue
        queue.append({
            'line': line, 'counterpart': counterpart,
            'amount_foreign': alt_diff, 'date': exchange_date,
        })

    @api.model
    def _create_exchange_difference_moves(self, exchange_diff_values_list):
        """Runs `super()` first (native entries, already carrying injected
        alternate amounts), then flushes the standalone-entry queue.
        """
        exchange_moves = super()._create_exchange_difference_moves(exchange_diff_values_list)

        # Popped BEFORE processing, in a `try/finally` -- same reasoning as
        # `l10n_ve_exchange_difference._create_exchange_difference_moves`:
        # this is plain cursor state, not ORM-transactional, so it must
        # never survive a savepoint rollback (a failed entry creation)
        # into the next attempt on the same cursor.
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
        """The exact `account.partial.reconcile` these two specific LINES
        (not just moves -- a line-level match is precise even across
        several installments, since each installment normally involves a
        fresh payment line) became, once core has created it -- available
        by the time this runs (`_create_exchange_difference_moves`, AFTER
        core's own partial-creation step).
        """
        self.ensure_one()
        return self.env['account.partial.reconcile'].search([
            ('debit_move_id', 'in', (self.id, counterpart.id)),
            ('credit_move_id', 'in', (self.id, counterpart.id)),
        ], order='id desc', limit=1)

    def _create_standalone_foreign_exchange_difference_entry(self, counterpart, amount_foreign, entry_date):
        """Posts core's same two-line exchange-difference shape (same
        accounts/journal) with zero company-currency amounts and only
        `foreign_debit`/`foreign_credit` set. Not reconciled against the
        original line -- there is no company-currency residual to close.

        Idempotency and reversal both ride on the NATIVE
        `account.partial.reconcile.exchange_move_id` field -- the same one
        core's own generic entries use, and core ALREADY reverses it
        automatically when the partial is removed
        (`account.partial.reconcile.unlink()`, core). No custom key or
        override needed: if this exact partial already has an
        `exchange_move_id`, reuse it; otherwise create the entry and
        claim it.
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