from odoo import api, models
from odoo.tools import formatLang


class AccountMove(models.Model):
    """Deductible figures of the totals: reference amount, widget rows."""

    _inherit = "account.move"

    @api.depends(
        "is_deductible",
        "global_deductible_type",
        "global_deductible_percent",
        "global_deductible_amount",
        "currency_id",
        "invoice_line_ids.price_unit",
        "invoice_line_ids.quantity",
        "invoice_line_ids.display_type",
    )
    def _compute_deductible_reference_amount(self):
        for move in self:
            amount = 0.0
            if move.is_deductible and move.global_deductible_type == "percent":
                amount = move._get_deductible_gross_total() * move.global_deductible_percent / 100.0
            elif move.is_deductible:
                amount = move.global_deductible_amount
            currency = move.currency_id
            move.global_deductible_reference_amount = currency.round(amount) if currency else amount

    @api.depends("invoice_line_ids.global_deductible_discount_percent")
    def _compute_company_currency_line_totals(self):
        return super()._compute_company_currency_line_totals()

    @api.depends(
        "is_deductible",
        "global_deductible_type",
        "global_deductible_percent",
        "global_deductible_amount",
        "invoice_line_ids.global_deductible_discount_percent",
        "invoice_line_ids.foreign_subtotal",
    )
    def _compute_tax_totals(self):
        """Add to `tax_totals` the subtotal without deductible and the
        deductible in the three currencies of the widgets. The deductible is
        converted exactly, so original - deductible == the booked subtotal."""
        super()._compute_tax_totals()
        for move in self.filtered("is_deductible"):
            if move.tax_totals:
                move.tax_totals = {**move.tax_totals, **move._get_deductible_totals(move.tax_totals)}

    def _get_deductible_totals(self, totals):
        """Values added to `tax_totals`: for each currency (document, company
        and foreign) the formatted subtotal without deductible and deductible."""
        self.ensure_one()
        company, line = self.company_id, self._get_deductible_product_lines()[:1]
        deducted, foreign = self.global_deductible_reference_amount, self.foreign_currency_id
        deducted_ves = company.currency_id.round(deducted / (line.currency_rate or 1.0))
        deducted_foreign = 0.0
        if foreign and line:
            converted = self.currency_id._convert(
                deducted, foreign, company, line._get_foreign_rate_date(), round=False
            )
            deducted_foreign = foreign.round(converted)
        by_suffix = {
            "currency": (self.currency_id, totals.get("base_amount_currency", 0.0), deducted),
            "ves": (company.currency_id, totals.get("base_amount", 0.0), deducted_ves),
            "foreign": (foreign, totals.get("base_amount_foreign_currency", 0.0), deducted_foreign),
        }
        values = {"is_deductible": True}
        for suffix, (currency, base, amount) in by_suffix.items():
            for key, value in (("original", base + amount), ("amount", amount)):
                values[f"formatted_deductible_{key}_{suffix}"] = formatLang(
                    self.env, value, currency_obj=currency
                )
        return values
