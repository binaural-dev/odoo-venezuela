from odoo import api, models
from odoo.tools import formatLang


class AccountTax(models.Model):
    _inherit = "account.tax"

    def _prepare_base_line_for_taxes_computation(self, record, **kwargs):
        res = super()._prepare_base_line_for_taxes_computation(record, **kwargs)
        # A fixed amount discount on a sale line feeds the tax engine through
        # its exact % equivalent (same criterion as account.move.line).
        if (
            record
            and not isinstance(record, dict)
            and record._name == "sale.order.line"
            and record._uses_discount_fixed()
        ):
            res["discount"] = record._get_exact_discount_percentage()
        return res

    @api.model
    def _get_tax_totals_summary(self, base_lines, currency, company, cash_rounding=None):
        res = super()._get_tax_totals_summary(base_lines, currency, company, cash_rounding)
        if self.env.context.get("l10n_ve_skip_global_discount") or not base_lines:
            return res
        first = base_lines[0].get("record")
        if not isinstance(first, models.Model):
            return res
        document = first.order_id if first._name == "sale.order.line" else (
            first.move_id if first._name == "account.move.line" else False
        )
        if (
            document
            and "discount_mode" in document._fields
            and document.discount_mode == "global_subtotal"
            and (document._name == "sale.order" or document.move_type == "out_invoice")
        ):
            self._add_global_subtotal_discount_info(res, base_lines, document, currency, company)
            return res
        if (
            not document
            or "discount_mode" not in document._fields
            or document.discount_mode != "global_total"
            or (
                document._name == "account.move"
                and document.move_type not in ("out_invoice", "out_refund")
            )
        ):
            return res
        total_before = res.get("total_amount_currency", 0.0)
        discount = document._get_global_total_discount(total_before, currency)
        if currency.is_zero(discount):
            return res
        ratio = discount / total_before
        discount_company = company.currency_id.round(res.get("total_amount", 0.0) * ratio)
        res["global_discount_mode"] = "global_total"
        res["global_discount_amount_currency"] = discount
        res["global_discount_amount"] = discount_company
        res["global_discount_type"] = document.global_discount_type
        res["global_discount_percent"] = document.global_discount_percent
        res["total_before_global_discount_currency"] = total_before
        res["total_amount_currency"] = total_before - discount
        res["total_amount"] = res.get("total_amount", 0.0) - discount_company
        foreign_currency = company.foreign_currency_id
        foreign_total = res.get("total_amount_foreign_currency")
        if foreign_total:
            foreign_discount = foreign_currency.round(foreign_total * ratio)
            res["global_discount_amount_foreign_currency"] = foreign_discount
            res["total_amount_foreign_currency"] = foreign_total - foreign_discount
            res["formatted_global_discount_foreign_currency"] = formatLang(
                self.env, foreign_discount, currency_obj=foreign_currency
            )
            res["formatted_total_amount_foreign_currency"] = formatLang(
                self.env, res["total_amount_foreign_currency"], currency_obj=foreign_currency
            )
        res["formatted_global_discount"] = formatLang(self.env, discount, currency_obj=currency)
        res["formatted_global_discount_ves"] = formatLang(
            self.env, discount_company, currency_obj=company.currency_id
        )
        res["formatted_total_amount_currency"] = formatLang(
            self.env, res["total_amount_currency"], currency_obj=currency
        )
        res["formatted_total_amount_currency_ves"] = formatLang(
            self.env, abs(res["total_amount"]), currency_obj=company.currency_id
        )
        return res

    def _add_global_subtotal_discount_info(self, res, base_lines, document, currency, company):
        """Rows for a global discount over the subtotal. The lines already carry
        the discount, so the totals are right; this only exposes how much it
        was, to show it in the totals widget and the reports."""
        discount = currency.round(
            sum(
                line.get("price_unit", 0.0) * line.get("quantity", 0.0) * line.get("discount", 0.0) / 100
                for line in base_lines
            )
        )
        if currency.is_zero(discount):
            return
        base = res.get("base_amount_currency", 0.0)
        res["global_discount_mode"] = "global_subtotal"
        res["global_discount_type"] = document.global_discount_type
        res["global_discount_percent"] = document.global_discount_percent
        res["global_discount_amount_currency"] = discount
        res["formatted_global_discount"] = formatLang(self.env, discount, currency_obj=currency)
        res["formatted_subtotal_before_global_discount"] = formatLang(
            self.env, base + discount, currency_obj=currency
        )
        ratio_company = res.get("base_amount", 0.0) / base if base else 1.0
        discount_company = company.currency_id.round(discount * ratio_company)
        res["global_discount_amount"] = discount_company
        res["formatted_global_discount_ves"] = formatLang(
            self.env, discount_company, currency_obj=company.currency_id
        )
        res["formatted_subtotal_before_global_discount_ves"] = formatLang(
            self.env, res.get("base_amount", 0.0) + discount_company, currency_obj=company.currency_id
        )
        foreign_base = res.get("base_amount_foreign_currency")
        foreign_currency = company.foreign_currency_id
        if foreign_base and base and foreign_currency:
            foreign_discount = foreign_currency.round(discount * foreign_base / base)
            res["global_discount_amount_foreign_currency"] = foreign_discount
            res["formatted_global_discount_foreign_currency"] = formatLang(
                self.env, foreign_discount, currency_obj=foreign_currency
            )
            res["formatted_subtotal_before_global_discount_foreign_currency"] = formatLang(
                self.env, foreign_base + foreign_discount, currency_obj=foreign_currency
            )
