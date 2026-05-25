from odoo import api, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.misc import formatLang

import logging

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _prepare_tax_totals(
        self, base_lines, currency, tax_lines=None, is_company_currency_requested=False
    ):
        res = super()._prepare_tax_totals(
            base_lines,
            currency,
            tax_lines,
            is_company_currency_requested=is_company_currency_requested,
        )

        currency = self.env.company.currency_foreign_id or currency
        move = self._get_move_from_base_lines(base_lines)
        
        has_foreign_fields = move and hasattr(move, 'foreign_total_billed') and move.foreign_total_billed
        foreign_amount_total = move.foreign_total_billed if has_foreign_fields else 0.0

        amount_untaxed_bs = res.get('amount_untaxed', 0.0)
        amount_total_bs = res.get('amount_total', 0.0)

        if amount_total_bs > 0.0:
            factor_neto = amount_untaxed_bs / amount_total_bs
            foreign_amount_untaxed = foreign_amount_total * factor_neto
        else:
            foreign_amount_untaxed = foreign_amount_total

        groups_by_foreign_subtotal = {}
        for subtotal_title, tax_groups in res.get('groups_by_subtotal', {}).items():
            foreign_groups = []
            for group in tax_groups:
                group_base_bs = group.get('tax_group_base_amount', 0.0)
                group_amount_bs = group.get('tax_group_amount', 0.0)
                
                factor_base = group_base_bs / amount_untaxed_bs if amount_untaxed_bs > 0.0 else 0.0
                factor_tax = group_amount_bs / amount_untaxed_bs if amount_untaxed_bs > 0.0 else 0.0

                foreign_base = foreign_amount_untaxed * factor_base
                foreign_tax_amount = foreign_amount_untaxed * factor_tax

                foreign_groups.append({
                    **group,
                    'tax_group_base_amount': foreign_base,
                    'tax_group_amount': foreign_tax_amount,
                    'formatted_tax_group_base_amount': formatLang(self.env, foreign_base, currency_obj=currency),
                    'formatted_tax_group_amount': formatLang(self.env, foreign_tax_amount, currency_obj=currency),
                })
            groups_by_foreign_subtotal[subtotal_title] = foreign_groups

        foreign_subtotals = []
        for subtotal in res.get('subtotals', []):
            subtotal_amount_bs = subtotal.get('amount', 0.0)
            factor_sub = subtotal_amount_bs / amount_untaxed_bs if amount_untaxed_bs > 0.0 else 0.0
            foreign_sub_amount = foreign_amount_untaxed * factor_sub
            
            foreign_subtotals.append({
                **subtotal,
                'amount': foreign_sub_amount,
                'formatted_amount': formatLang(self.env, foreign_sub_amount, currency_obj=currency),
            })

        total_gross_bs = sum((line.price_unit * line.quantity) for line in move.invoice_line_ids) if move else 0.0
        discount_amount_bs = total_gross_bs - amount_untaxed_bs if total_gross_bs > amount_untaxed_bs else 0.0
        
        if total_gross_bs > 0.0:
            factor_discount = discount_amount_bs / total_gross_bs
            foreign_gross_amount = foreign_amount_untaxed / (1.0 - factor_discount) if factor_discount < 1.0 else 0.0
            foreign_discount_amount = foreign_gross_amount * factor_discount
        else:
            foreign_discount_amount = 0.0

        res.update({
            "groups_by_foreign_subtotal": groups_by_foreign_subtotal,
            "foreign_subtotals": foreign_subtotals,
            "foreign_amount_untaxed": foreign_amount_untaxed,
            "foreign_amount_total": foreign_amount_total,
            "foreign_formatted_amount_untaxed": formatLang(self.env, foreign_amount_untaxed, currency_obj=currency),
            "foreign_formatted_amount_total": formatLang(self.env, foreign_amount_total, currency_obj=currency),
            
            "foreign_subtotal": foreign_amount_untaxed + foreign_discount_amount,
            "foreign_formatted_subtotal": formatLang(self.env, foreign_amount_untaxed + foreign_discount_amount, currency_obj=currency),
            "foreign_discount_amount": foreign_discount_amount,
            "foreign_formatted_discount_amount": formatLang(self.env, foreign_discount_amount, currency_obj=currency),
            "show_discount": self.env.company.show_discount_on_moves,
        })

        amounts_paid = self._get_total_paid_foreign(move, currency) if move else []
        res["foreign_total_amount_paid"] = sum(amounts_paid)
        
        foreign_total_residual = foreign_amount_total - res["foreign_total_amount_paid"]
        res["foreign_total_residual"] = max(0.0, foreign_total_residual)
        
        res["foreign_formatted_total_residual"] = formatLang(
            self.env,
            res["foreign_total_residual"],
            currency_obj=currency
        )            

        return res

    def _get_move_from_base_lines(self, base_lines):
        for l in (base_lines or []):
            r = l.get("record")
            if not r:
                continue

            if getattr(r, "_name", None) == "account.move":
                return r

            if "move_id" in getattr(r, "_fields", {}):
                if r.move_id:
                    return r.move_id
        return None

    def _get_total_paid_foreign(self, move, foreign_currency):
        if not move or not move.invoice_payments_widget:
            return []

        amounts = []
        # Odoo almacena esto como dict o como string JSON dependiendo de la versión/estado
        widget_data = move.invoice_payments_widget
        content = widget_data.get('content') or []

        for payment in content:
            # Extraemos directamente el valor que vemos en tu imagen
            # Usamos .get() por seguridad si el campo no existe en algún pago
            f_amount = payment.get('foreign_amount', 0.0)

            # Opcional: Validar que el pago sea de la moneda que buscas
            # En tu imagen sale 'foreign_id': 2
            amounts.append(f_amount)

        return amounts

    def get_foreign_base_tax_lines(self, base_lines, tax_lines, currency):
        foreign_base_lines = [line.copy() for line in base_lines if line]
        foreign_tax_lines = None
        if tax_lines:
            foreign_tax_lines = [line.copy() for line in tax_lines if line]
        taxes = []
        for base_line in foreign_base_lines:
            is_exists_foreign_price = "foreign_price" in base_line["record"]

            if is_exists_foreign_price:
                base_line["price_unit"] = base_line["record"].foreign_price
                base_line["price_subtotal"] = base_line["record"].foreign_subtotal
                base_line["currency"] = currency
            else:
                base_line["price_unit"] = base_line["record"].price_unit
                base_line["price_subtotal"] = base_line["record"].price_subtotal
                base_line["currency"] = base_line["record"].currency_id

            if base_line["taxes"]:
                taxes.append(
                    {
                        "tax": base_line["taxes"][0],
                        "price": base_line["price_unit"],
                        "base": base_line["price_subtotal"],
                    }
                )

        tax_values_list = []
        for base_line in foreign_base_lines:
            tax_values_list += self._compute_taxes_for_single_line(base_line)[1]

        round_globally = self.env.company.tax_calculation_rounding_method == "round_globally"

        if foreign_tax_lines:
            for tax_line in foreign_tax_lines:
                tax_line["currency"] = currency
                tax_line["tax_amount"] = 0.0
                amount = 0.0
                for tax in tax_values_list:
                    if tax["tax_repartition_line"].id == tax_line["tax_repartition_line"].id:
                        if not round_globally:
                            amount += tax["amount"]
                        else:
                            amount += tax["amount"]

                tax_line["tax_amount"] = amount
                

        return foreign_base_lines, foreign_tax_lines

    