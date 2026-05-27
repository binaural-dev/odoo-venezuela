from odoo.tools.float_utils import float_round, float_compare
from odoo import api, models, _, fields
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
        """This function adds the alternate currency tax amounts to tax_totals.

        It features an adaptive currency matrix that accurately determines whether to
        multiply or divide to calculate alternate values (USD or VEF), ensuring precise
        proportions without performance-heavy redundant loops.
        """
        is_manual_edit = self.env.context.get('real_portion_manual_edit', False)
        
        foreign_currency = self.env.company.currency_foreign_id or False
        if not foreign_currency:
            raise ValidationError(_("No foreign currency configured in the company"))

        # 1. Base Currency: Único llamado nativo necesario
        res = super()._prepare_tax_totals(
            base_lines,
            currency,
            tax_lines,
            is_company_currency_requested=is_company_currency_requested,
        )

        # 2. Capturar el move para extraer la tasa inversa de la Porción Real
        move = self._get_move_from_base_lines(base_lines)
        inverse_rate = move.foreign_inverse_rate if move and hasattr(move, "foreign_inverse_rate") else 0.0
        
        if inverse_rate <= 0.0:
            inverse_rate = foreign_currency._get_conversion_rate(
                self.env.company.currency_id,
                foreign_currency,
                self.env.company,
                move.date if move else fields.Date.today(),
            ) or 1.0

        # =========================================================================
        # CORRECCIÓN CRÍTICA: MATRIZ DINÁMICA DE CONVERSIÓN 
        # =========================================================================
        # Evaluamos las monedas por su código/identificador para evitar fallas de contexto.
        # 'currency' es la moneda de la factura actual. 'foreign_currency' es la alterna.
        
        if currency == foreign_currency:
            # Si la factura ya está en la moneda alterna, el alterno debe ser la moneda base.
            # Por ende, para pasar de la alterna (ej. VEF) a la base (ej. USD), se DIVIDE entre la tasa.
            multiply_dir = False
        else:
            # Si la factura está en la moneda base (ej. USD) y queremos la alterna (ej. VEF), se MULTIPLICA.
            # Si la factura está en una moneda x y la alterna es la débil (VEF), típicamente multiplicamos por la tasa.
            multiply_dir = True

        # Seguridad extrema contra tasas en cero para evitar caídas del sistema
        if inverse_rate == 0.0:
            inverse_rate = 1.0
        # =========================================================================

        # 3. Procesar importes globales alternos aplicando la dirección corregida
        #foreign_amount_untaxed = foreign_currency.round(res["amount_untaxed"] * inverse_rate if multiply_dir else res["amount_untaxed"] / inverse_rate)
        #foreign_amount_total = foreign_currency.round(res["amount_total"] * inverse_rate if multiply_dir else res["amount_total"] / inverse_rate)
        is_manual_edit = self.env.context.get('real_portion_manual_edit', False)

        if is_manual_edit and move and move.invoice_line_ids:
            # Si el usuario editó un precio foráneo, SUMAMOS la masa real de la interfaz.
            # No usamos la tasa porque la masa foránea ahora es independiente.
            valid_lines = move.invoice_line_ids.filtered(lambda l: l.display_type not in ('line_section', 'line_note'))
            
            foreign_amount_untaxed = sum(getattr(l, 'foreign_subtotal', 0.0) for l in valid_lines)
            foreign_amount_total = sum(getattr(l, 'foreign_price_total', 0.0) for l in valid_lines)
            
            # Calculamos una tasa efectiva global basada en el IVA real acumulado de las líneas
            # para que los grupos de impuestos inferiores se cuadren al centavo con la masa manual.
            native_tax_total = res["amount_total"] - res["amount_untaxed"]
            foreign_tax_total = foreign_amount_total - foreign_amount_untaxed
            
            effective_tax_rate = foreign_tax_total / native_tax_total if native_tax_total > 0.0 else inverse_rate
        else:
            # Flujo Automático Tradicional (Usa la conversión teórica por tasa)
            foreign_amount_untaxed = res["amount_untaxed"] * inverse_rate if multiply_dir else res["amount_untaxed"] / inverse_rate
            foreign_amount_total = res["amount_total"] * inverse_rate if multiply_dir else res["amount_total"] / inverse_rate
            effective_tax_rate = inverse_rate

        foreign_amount_untaxed = foreign_currency.round(foreign_amount_untaxed)
        foreign_amount_total = foreign_currency.round(foreign_amount_total)
        # 4. Mapear 'groups_by_foreign_subtotal' iterando sobre los grupos nativos
        groups_by_foreign_subtotal = {}
        for subtotal_title, tax_groups in res.get("groups_by_subtotal", {}).items():
            f_groups = []
            for group in tax_groups:
                f_base = foreign_currency.round(group["tax_group_base_amount"] * inverse_rate if multiply_dir else group["tax_group_base_amount"] / inverse_rate)
                #f_tax = foreign_currency.round(group["tax_group_amount"] * inverse_rate if multiply_dir else group["tax_group_amount"] / inverse_rate)
                # El impuesto del grupo se recalcula usando la tasa efectiva de la masa de las líneas
                if is_manual_edit:
                    f_tax = foreign_currency.round(group["tax_group_amount"] * effective_tax_rate)
                else:
                    f_tax = foreign_currency.round(group["tax_group_amount"] * inverse_rate if multiply_dir else group["tax_group_amount"] / inverse_rate)

                f_groups.append({
                    **group,
                    "tax_group_base_amount": f_base,
                    "tax_group_amount": f_tax,
                    "formatted_tax_group_base_amount": formatLang(self.env, f_base, currency_obj=foreign_currency),
                    "formatted_tax_group_amount": formatLang(self.env, f_tax, currency_obj=foreign_currency),
                })
            groups_by_foreign_subtotal[subtotal_title] = f_groups

        # 5. Mapear 'foreign_subtotals' iterando sobre los subtotales nativos
        foreign_subtotals = []
        for subtotal in res.get("subtotals", []):
            #f_sub_amt = foreign_currency.round(subtotal["amount"] * inverse_rate if multiply_dir else subtotal["amount"] / inverse_rate)
            if is_manual_edit:
                # Si es manual, reflejamos directamente el monto untaxed consolidado de las líneas
                f_sub_amt = foreign_amount_untaxed
            else:
                f_sub_amt = foreign_currency.round(subtotal["amount"] * inverse_rate if multiply_dir else subtotal["amount"] / inverse_rate)

            foreign_subtotals.append({
                **subtotal,
                "amount": f_sub_amt,
                "formatted_amount": formatLang(self.env, f_sub_amt, currency_obj=foreign_currency),
            })

        # 6. Gestión de Descuentos (Base y Alterno)
        res_without_discount_untaxed = res["amount_untaxed"]
        has_discount = not currency.is_zero(sum([line.get("discount", 0.0) for line in base_lines if "discount" in line]))

        if has_discount and move:
            total_gross_local = sum((line.price_unit * line.quantity) for line in move.invoice_line_ids)
            if total_gross_local > res["amount_untaxed"]:
                res_without_discount_untaxed = total_gross_local

        #foreign_subtotal = foreign_currency.round(res_without_discount_untaxed * inverse_rate if multiply_dir else res_without_discount_untaxed / inverse_rate)
        if is_manual_edit and move and move.invoice_line_ids:
            valid_lines = move.invoice_line_ids.filtered(lambda l: l.display_type not in ('line_section', 'line_note'))
            # Sumamos los precios extranjeros directos multiplicados por la cantidad (antes de descuento)
            foreign_subtotal = sum((l.foreign_price * l.quantity) for l in valid_lines)
        else:
            foreign_subtotal = res_without_discount_untaxed * inverse_rate if multiply_dir else res_without_discount_untaxed / inverse_rate

        # 7. Inyección de valores en el diccionario 'res' conservando tus claves originales
        res["groups_by_foreign_subtotal"] = groups_by_foreign_subtotal
        res["foreign_subtotals"] = foreign_subtotals
        res["foreign_amount_untaxed"] = foreign_amount_untaxed
        res["foreign_amount_total"] = foreign_amount_total
        res["foreign_formatted_amount_untaxed"] = formatLang(self.env, foreign_amount_untaxed, currency_obj=foreign_currency)
        res["foreign_formatted_amount_total"] = formatLang(self.env, foreign_amount_total, currency_obj=foreign_currency)

        res["show_discount"] = self.env.company.show_discount_on_moves

        res["subtotal"] = res_without_discount_untaxed
        res["formatted_subtotal"] = formatLang(self.env, res["subtotal"], currency_obj=currency)

        res["foreign_subtotal"] = foreign_subtotal
        res["foreign_formatted_subtotal"] = formatLang(self.env, res["foreign_subtotal"], currency_obj=foreign_currency)

        res["discount_amount"] = res["amount_untaxed"] - res_without_discount_untaxed
        res["formatted_discount_amount"] = formatLang(self.env, res["discount_amount"], currency_obj=currency)
        
        res["foreign_discount_amount"] = foreign_amount_untaxed - foreign_subtotal
        res["foreign_formatted_discount_amount"] = formatLang(self.env, res["foreign_discount_amount"], currency_obj=foreign_currency)

        # 8. Pagos y Residuales Alternos
        amounts = self._get_total_paid_foreign(move, foreign_currency) if move else []
        res["foreign_total_amount_paid"] = sum(amounts)
           
        res["foreign_total_residual"] = foreign_amount_total - res["foreign_total_amount_paid"]

        formatted_result = 0 if float_compare(res['foreign_total_residual'], 0, precision_digits=foreign_currency.decimal_places) < 0 else res['foreign_total_residual']
        res["foreign_formatted_total_residual"] = formatLang(
            self.env,
            formatted_result,
            currency_obj=foreign_currency
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
        widget_data = move.invoice_payments_widget
        content = widget_data.get('content') or []

        for payment in content:
            f_amount = payment.get('foreign_amount', 0.0)

            amounts.append(f_amount)

        return amounts

    