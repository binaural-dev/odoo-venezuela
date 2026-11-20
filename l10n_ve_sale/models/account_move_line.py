from collections import defaultdict

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, frozendict

from .l10n_ve_discount_document import is_discount_applying


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _get_discount_move(self, vals=None):
        move = self.move_id
        if not move and vals and vals.get("move_id"):
            move = self.env["account.move"].browse(vals["move_id"])
        return move

    def _get_line_discount_type(self, company=None, vals=None):
        move = self._get_discount_move(vals)
        if move and move.discount_mode:
            return move._get_doc_discount_type()
        return super()._get_line_discount_type(company=company, vals=vals)

    def _check_move_not_locked_by_approval(self, moves=None):
        """The lines of an invoice waiting for a discount approval are locked."""
        if self.env.su or is_discount_applying(self.env):
            return
        moves = moves if moves is not None else self.move_id
        waiting = moves._discount_is_waiting()
        if waiting:
            raise UserError(waiting[:1]._discount_locked_message())

    @api.model_create_multi
    def create(self, vals_list):
        self._check_move_not_locked_by_approval(
            self.env["account.move"].browse([v["move_id"] for v in vals_list if v.get("move_id")])
        )
        for vals in vals_list:
            if "discount" not in vals and "discount_fixed" not in vals:
                continue
            move = self.env["account.move"].browse(vals.get("move_id"))
            if move and move.move_type == "out_invoice":
                move._discount_guard(vals)
        lines = super().create(vals_list)
        if any("discount" in v or "discount_fixed" in v for v in vals_list):
            lines.move_id.filtered(
                lambda m: m.move_type == "out_invoice"
            )._evaluate_discount_approval()
        return lines

    def write(self, vals):
        if not all(key.startswith(("message_", "activity_")) for key in vals):
            self._check_move_not_locked_by_approval()
        if "discount" in vals or "discount_fixed" in vals:
            for move in self.move_id.filtered(lambda m: m.move_type == "out_invoice"):
                move._discount_guard(vals)
        res = super().write(vals)
        if ("discount" in vals or "discount_fixed" in vals) and not is_discount_applying(
            self.env
        ):
            self.move_id.filtered(
                lambda m: m.move_type == "out_invoice"
            )._evaluate_discount_approval()
        if {"price_unit", "quantity", "product_id"} & set(vals):
            self.move_id.filtered(
                lambda m: m.move_type == "out_invoice"
            )._reapply_global_discount()
        return res

    def unlink(self):
        self._check_move_not_locked_by_approval()
        moves = self.move_id.filtered(lambda m: m.move_type == "out_invoice")
        res = super().unlink()
        moves.exists()._reapply_global_discount()
        return res

    @api.depends(
        "discount_fixed",
        "move_id.discount_mode",
        "move_id.line_ids.discount_fixed",
        "move_id.line_ids.price_total",
        "move_id.global_discount_type",
        "move_id.global_discount_percent",
        "move_id.global_discount_amount",
        "move_id.global_total_discount",
        "move_id.global_total_discount_company",
    )
    def _compute_discount_allocation_needed(self):
        """The native allocation only knows the % field. Lines discounted
        with a fixed amount (line scheme or global over the subtotal) get the
        same allocation entry, computed from the exact % equivalent."""
        super()._compute_discount_allocation_needed()
        for move in self.move_id.filtered(
            lambda m: m._is_global_total_move()
        ):
            first = move.line_ids.filtered(lambda l: l.display_type == "product")[:1]
            if first and first in self:
                first.discount_allocation_needed = first._get_global_total_discount_needed()
        self._apply_discount_allocation_amounts(
            self._get_fixed_discount_allocation_amounts()
        )

    def _get_fixed_discount_allocation_amounts(self):
        """{line: [(account, amount_currency, balance), ...]} of the lines
        discounted with a fixed amount: what the native computation would give
        for their exact % equivalent (same cumulative rounding per account).
        Covered by a parity test against the native percentage path, so a
        change of the native computation shows up when migrating."""
        line2amounts = {}
        cumulated = defaultdict(float)
        for line in self.move_id.line_ids:
            account = (
                line.display_type == "product"
                and line._uses_discount_fixed()
                and line.move_id._get_discount_allocation_account()
            )
            if not account or line.account_id == account:
                continue
            base_line = line.move_id._prepare_product_base_line_for_taxes_computation(line)
            base_line["discount"] = 0.0
            self.env["account.tax"]._add_tax_details_in_base_line(base_line, line.company_id)
            gross = base_line["tax_details"]["raw_total_excluded_currency"]
            key = (line.move_id, line.account_id)
            previous = line.currency_id.round(cumulated[key])
            cumulated[key] += (
                line.move_id.direction_sign
                * gross
                * line._get_exact_discount_percentage()
                / 100
            )
            current = line.currency_id.round(cumulated[key])
            amount_currency = current - previous
            amount = line.company_currency_id.round(
                current / line.currency_rate
            ) - line.company_currency_id.round(previous / line.currency_rate)
            if amount_currency or amount:
                line2amounts[line] = [
                    (line.account_id, amount_currency, amount),
                    (account, -amount_currency, -amount),
                ]

        return line2amounts

    def _apply_discount_allocation_amounts(self, line2amounts):
        """Turns the allocation amounts into `discount_allocation_needed`
        (same structure the native computation fills)."""
        totals = defaultdict(lambda: defaultdict(float))
        for line, entries in line2amounts.items():
            for account, _amount_currency, amount in entries:
                for analytic_id, percentage in (line.analytic_distribution or {}).items():
                    totals[
                        frozendict(
                            {
                                "move_id": line.move_id.id,
                                "account_id": account.id,
                                "currency_rate": line.currency_rate,
                            }
                        )
                    ][analytic_id] += amount * percentage / 100

        for line in self:
            if line not in line2amounts:
                continue
            needed = {}
            for account, amount_currency, amount in line2amounts[line]:
                key = frozendict(
                    {
                        "move_id": line.move_id.id,
                        "account_id": account.id,
                        "currency_rate": line.currency_rate,
                    }
                )
                dist = totals[key]
                total = sum(dist.values()) or 1
                needed[key] = frozendict(
                    {
                        "display_type": "discount",
                        "name": _("Discount"),
                        "amount_currency": amount_currency,
                        "balance": amount,
                        "analytic_distribution": {
                            analytic_id: 100 * value / total
                            for analytic_id, value in dist.items()
                        },
                    }
                )
            line.discount_allocation_needed = needed

    # ------------------------------------------------------------------
    # Alternate currency of the discount entries
    # ------------------------------------------------------------------
    def _get_foreign_value(self):
        """The discount allocation entries carry their alternate-currency
        amounts too, calculated the way l10n_ve_accountant calculates the ones
        of the product lines (from the alternate price of each line)."""
        self.ensure_one()
        if self.display_type == "discount":
            return self._get_discount_foreign_value()
        return super()._get_foreign_value()

    def _get_move_foreign_discount(self):
        """Discount of the whole document in the alternate currency.

        Over the subtotal (or on the lines): what the product lines lose in
        alternate currency, as their own alternate subtotal says (alternate
        gross - alternate subtotal). Over the total: the share of the document
        total, with the alternate total of its lines (`foreign_price_total`)."""
        self.ensure_one()
        move = self.move_id
        foreign = self.company_id.foreign_currency_id
        products = move.line_ids.filtered(lambda line: line.display_type == "product")
        if move._is_global_total_move():
            total = sum(products.mapped("price_total"))
            if float_is_zero(total, precision_rounding=move.currency_id.rounding):
                return 0.0
            return foreign.round(
                move.global_total_discount * sum(products.mapped("foreign_price_total")) / total
            )
        lost = sum(
            foreign.round(line.foreign_price * line.quantity) - line.foreign_subtotal
            for line in products
            if line._get_effective_discount_percent()
        )
        return foreign.round(lost)

    def _get_discount_foreign_value(self):
        """Signed (+ debit) alternate amount of this discount entry: the foreign
        discount of the document spread over the entries of its own side in
        proportion to their balance, the last one taking the rounding so both
        sides add up exactly."""
        self.ensure_one()
        foreign = self.company_id.foreign_currency_id
        if not foreign or not self.balance:
            return 0.0
        total_foreign = self._get_move_foreign_discount()
        debit_side = self.balance > 0
        side = self.move_id.line_ids.filtered(
            lambda line: line.display_type == "discount" and line.balance and (line.balance > 0) == debit_side
        )
        side = side.sorted(lambda line: line._origin.id or 0)
        total_balance = sum(abs(line.balance) for line in side)
        remaining = total_foreign
        share = 0.0
        for index, line in enumerate(side):
            if index == len(side) - 1:
                amount = remaining
            else:
                amount = foreign.round(total_foreign * abs(line.balance) / total_balance)
                remaining -= amount
            if line == self or (line._origin and line._origin == self._origin):
                share = amount
        return share if debit_side else -share

    def _get_global_total_discount_needed(self):
        """Journal item of a global discount over the total: one debit on the
        global discount account. Income and taxes stay as they are, so the
        receivable ends up lowered by the discount."""
        move = self.move_id
        account = move.company_id.global_discount_account_id
        if not account:
            return {}
        discount, discount_company = move._get_global_total_discount_amounts()
        if move.currency_id.is_zero(discount):
            return {}
        amount_currency = -move.direction_sign * discount
        balance = -move.direction_sign * discount_company
        key = frozendict(
            {"move_id": move.id, "account_id": account.id, "currency_rate": self[:1].currency_rate}
        )
        return {
            key: frozendict(
                {
                    "display_type": "discount",
                    "name": _("Global discount"),
                    "amount_currency": amount_currency,
                    "balance": balance,
                    "analytic_distribution": {},
                }
            )
        }
