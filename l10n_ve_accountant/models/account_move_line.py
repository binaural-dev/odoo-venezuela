import inspect
from odoo import api, fields, models, Command, _
from odoo.tools import float_compare
from odoo.exceptions import UserError, ValidationError
from collections import defaultdict

from datetime import date, timedelta
import traceback
from markupsafe import Markup
from odoo.tools import float_is_zero

import logging

_logger = logging.getLogger(__name__)

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    not_foreign_recalculate = fields.Boolean()
    foreign_currency_id = fields.Many2one(
        related="move_id.foreign_currency_id", store=True
    )
    foreign_rate = fields.Float(related="move_id.foreign_rate", store=True)
    foreign_inverse_rate = fields.Float(
        related="move_id.foreign_inverse_rate", store=True, index=True
    )

    foreign_price = fields.Monetary(
        help="Foreign Price of the line",
        compute="_compute_foreign_price",
        inverse="_inverse_foreign_price",
        currency_field="foreign_currency_id",
        store=True,
        readonly=False,
    )
    foreign_subtotal = fields.Monetary(
        help="Foreign Subtotal of the line",
        compute="_compute_foreign_price",
        currency_field="foreign_currency_id",
        store=True,
    )
    foreign_price_total = fields.Monetary(
        help="Foreign Total of the line",
        compute="_compute_foreign_price",
        currency_field="foreign_currency_id",
        store=True,
    )
    amount_currency = fields.Monetary(precompute=False)

    # Report fields
    foreign_debit = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_foreign_debit_credit",
        store=True,
        readonly=False
        
    )
    foreign_credit = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_foreign_debit_credit",
        store=True,
        readonly=False
    )

    foreign_debit_no_format = fields.Float()
    foreign_credit_no_format = fields.Float()

    foreign_balance = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_foreign_balance",
        inverse="_inverse_foreign_balance",
        store=True,
    )

    foreign_debit_adjustment = fields.Monetary(
        currency_field="foreign_currency_id",
        help="When setted, this field will be used to fill the foreign debit field",
    )
    foreign_credit_adjustment = fields.Monetary(
        currency_field="foreign_currency_id",
        help="When setted, this field will be used to fill the foreign credit field",
    )

    foreign_amount_residual = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_amount_residual",
        store=True,
        readonly=True,
    )
    foreign_amount_residual_currency = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_amount_residual",
        store=True,
        readonly=True,
    )


    def _inverse_foreign_price(self):
        """
        INVERSE POR CONTEXTO:
        Inyecta una bandera temporal en el hilo de ejecución para avisarle al compute
        que el cambio actual proviene del dedo del usuario.
        """
        for line in self:
            if line.display_type in ('line_section', 'line_note'):
                continue
            
            # Creamos un entorno protegido con nuestro contexto de edición manual
            context_env = line.move_id.line_ids.with_context(real_portion_manual_edit=True)
            
            # 2. Forzamos el cálculo de la Porción Real en todas las líneas de la cuadrícula
            context_env._compute_foreign_price()
            
           
        
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

    @api.depends("price_unit", 
        "foreign_inverse_rate", 
        "move_id.line_ids.price_unit",
        "quantity",
        "discount",
        "tax_ids",
        "price_subtotal",
        "price_total")
    def _compute_foreign_price(self):
        """
        PORCIÓN REAL CON REDISTRIBUCIÓN DE MASA:
        El contexto ahora llega blindado desde el write de account.move.
        Si es manual, recalcula las proporciones usando la masa extranjera actual.
        Si es automático, usa el price_unit nativo.
        """
        # El contexto ya no se pierde porque viaja en la raíz de la transacción
        is_manual_edit = self.env.context.get('real_portion_manual_edit', False)

        moves_mapped = defaultdict(lambda: self.env['account.move.line'])
        for line in self:
            moves_mapped[line.move_id] |= line

        for move, lines in moves_mapped.items():
            valid_lines = move.line_ids.filtered(
                lambda l: l.display_type not in ('line_section', 'line_note') and l.price_unit
            )

            if not valid_lines:
                for line in lines:
                    line.foreign_price = line.foreign_subtotal = line.foreign_price_total = 0.0
                continue

            rate = valid_lines[0].foreign_inverse_rate or 1.0
            last_line = valid_lines[-1]
            allocated_foreign_price = 0.0

            # =========================================================================
            # CONFIGURACIÓN DINÁMICA DEL PIVOTE DE MASA CONTABLE
            # =========================================================================
            if is_manual_edit:
                # Pivote Extranjero: El objetivo es la suma de lo que ya está en pantalla
                total_mass_pivote = sum(l.foreign_price for l in valid_lines)
                total_foreign_price_target = total_mass_pivote
            else:
                # Pivote Nativo: El objetivo es el techo teórico original por tasa
                total_mass_pivote = sum(l.price_unit for l in valid_lines)
                total_foreign_price_target = total_mass_pivote * rate

            # Procesamos TODAS las líneas bajo el peso del pivote seleccionado
            for line in valid_lines:
                if line in lines:
                    # Determinamos la proporción matemática según el flujo activo
                    if is_manual_edit:
                        proportion = line.foreign_price / total_mass_pivote if total_mass_pivote else 0.0
                    else:
                        proportion = line.price_unit / total_mass_pivote if total_mass_pivote else 0.0
                    
                    line.foreign_price = total_foreign_price_target * proportion

                    # Cálculo uniforme de subtotales y porción real de IVA
                    disc_price = line.foreign_price * (1 - (line.discount / 100.0))
                    line.foreign_subtotal = disc_price * line.quantity
                    porcion_iva = line.price_total / line.price_subtotal if line.price_subtotal > 0.0 else 1.0
                    line.foreign_price_total = line.foreign_subtotal * porcion_iva
                else:
                    line.foreign_price = line.foreign_price

                allocated_foreign_price += line.foreign_price

            # =========================================================================
            # AJUSTE POR SUSTRACCIÓN DE RESIDUO SOBRE LA ÚLTIMA LÍNEA
            # =========================================================================
            residual_difference = total_foreign_price_target - allocated_foreign_price
            
            if abs(residual_difference) > 0.0001 and last_line in lines:
                last_line.foreign_price += residual_difference
                
                disc_price = last_line.foreign_price * (1 - (last_line.discount / 100.0))
                last_line.foreign_subtotal = disc_price * last_line.quantity
                porcion_iva = last_line.price_total / last_line.price_subtotal if last_line.price_subtotal > 0.0 else 1.0
                last_line.foreign_price_total = last_line.foreign_subtotal * porcion_iva

    @api.depends(
        "debit",
        "credit",
        "foreign_subtotal",
        "foreign_balance",
        "foreign_price_total",
        "not_foreign_recalculate",
        "foreign_debit_adjustment",
        "foreign_credit_adjustment",
    )
    def _compute_foreign_debit_credit(self):
        for line in self:
            
            if line.not_foreign_recalculate:
                if line.foreign_debit_adjustment or line.foreign_credit_adjustment:
                    self._calculate_from_adjustment(line)
                continue

            if line.foreign_debit_adjustment or line.foreign_credit_adjustment:
                self._calculate_from_adjustment(line)

            elif line.display_type in ("line_section", "line_note"):
                self._calculate_zero(line)

            elif line.display_type == ("payment_term", "tax","product"):
                self._calculate_from_product(line)

            elif line.currency_id == line.company_id.currency_foreign_id and line.amount_currency:
                self._calculate_from_amount_currency(line)
            else:
                self._calculate_for_non_invoice(line)

    def _calculate_from_adjustment(self, line):
        new_foreign_debit = abs(line.foreign_debit_adjustment) if line.foreign_debit_adjustment else 0.0
        if line.foreign_debit != new_foreign_debit:

            line.foreign_debit = new_foreign_debit

        new_foreign_credit = abs(line.foreign_credit_adjustment) if line.foreign_credit_adjustment else 0.0

        if line.foreign_credit != new_foreign_credit:

            line.foreign_credit = new_foreign_credit         

    def _calculate_zero(self, line):
        """Asigna cero para secciones o notas."""
        if line.foreign_debit != 0.0:
            line.foreign_debit = 0.0
        if line.foreign_credit != 0.0:
            line.foreign_credit = 0.0

    def _calculate_from_amount_currency(self, line):
        new_foreign_debit = abs(line.amount_currency) if line.amount_currency > 0 else 0.0
        if line.foreign_debit != new_foreign_debit:
            line.foreign_debit = new_foreign_debit

        new_foreign_credit = abs(line.amount_currency) if line.amount_currency < 0 else 0.0
        if line.foreign_credit != new_foreign_credit:
            line.foreign_credit = new_foreign_credit


    def _calculate_for_non_invoice(self, line):
        """
        APLICACIÓN DE PORCIÓN REAL (LÍNEA POR LÍNEA):
        Calcula la masa global del asiento en memoria para determinar la porción real 
        exacta de esta línea o asignarle el residuo si es la última del asiento.
        """
        move = line.move_id
        
        # 1. Filtramos las líneas operativas del asiento entero para el cálculo global
        valid_lines = move.line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note')
        )
        if not valid_lines:
            return

        # 2. Determinar la tasa real única (Macro Tasa) del asiento
        rate_line = valid_lines.filtered(lambda l: l.foreign_inverse_rate)
        inverse_rate = rate_line[0].foreign_inverse_rate if rate_line else 0.0

        if inverse_rate == 0.0:
            foreign_currency = move.company_id.currency_foreign_id
            if foreign_currency:
                inverse_rate = foreign_currency._get_conversion_rate(
                    move.company_id.currency_id,
                    foreign_currency,
                    move.company_id,
                    move.date
                )
        inverse_rate = inverse_rate or 1.0

        # 3. Caso especial: Cuenta puente/cuadre con balance extranjero existente
        foreign_lines = move.line_ids.filtered(lambda l: l.currency_id == l.company_id.currency_foreign_id)
        currency_lines = move.line_ids.filtered(lambda l: l.currency_id == l.company_id.currency_id)
        bridge_balance = sum(foreign_lines.mapped("amount_currency"))

        if bridge_balance and len(currency_lines) == 1:
            if line in currency_lines:
                line.foreign_debit = abs(bridge_balance) if bridge_balance < 0 else 0.0
                line.foreign_credit = abs(bridge_balance) if bridge_balance > 0 else 0.0
                line.foreign_debit_no_format = line.foreign_debit
                line.foreign_credit_no_format = line.foreign_credit
            return

        # 4. DETERMINACIÓN DE LA PORCIÓN REAL
        last_line = valid_lines[-1]

        # Si la línea actual NO es la última, aplicamos el prorrateo puro de la porción real
        if line != last_line:
            total_local_debit = sum(l.debit for l in valid_lines)
            total_local_credit = sum(l.credit for l in valid_lines)
            
            target_foreign_debit = total_local_debit * inverse_rate
            target_foreign_credit = total_local_credit * inverse_rate

            prop_debit = line.debit / total_local_debit if total_local_debit else 0.0
            prop_credit = line.credit / total_local_credit if total_local_credit else 0.0

            line.foreign_debit = target_foreign_debit * prop_debit
            line.foreign_credit = target_foreign_credit * prop_credit
        
        # Si la línea actual ES la última, le toca absorber el residuo para cuadrar el asiento
        else:
            # Calculamos cuánto sumaron las líneas anteriores (recalculadas bajo la misma lógica)
            total_local_debit = sum(l.debit for l in valid_lines)
            total_local_credit = sum(l.credit for l in valid_lines)
            
            target_foreign_debit = total_local_debit * inverse_rate
            target_foreign_credit = total_local_credit * inverse_rate

            allocated_foreign_debit = 0.0
            allocated_foreign_credit = 0.0

            for l in valid_lines[:-1]:
                prop_d = l.debit / total_local_debit if total_local_debit else 0.0
                prop_c = l.credit / total_local_credit if total_local_credit else 0.0
                allocated_foreign_debit += target_foreign_debit * prop_d
                allocated_foreign_credit += target_foreign_credit * prop_c

            line.foreign_debit = max(0.0, target_foreign_debit - allocated_foreign_debit)
            line.foreign_credit = max(0.0, target_foreign_credit - allocated_foreign_credit)

        line.foreign_debit_no_format = line.foreign_debit
        line.foreign_credit_no_format = line.foreign_credit

    def _calculate_from_product(self, line):
        
        sign = line.move_id.direction_sign * -1
        amount = line.foreign_subtotal * sign
        new_foreign_debit = abs(amount) if amount < 0 else 0.0
        if line.foreign_debit != new_foreign_debit:
            line.foreign_debit = new_foreign_debit

        new_foreign_credit = abs(amount) if amount > 0 else 0.0
        if line.foreign_credit != new_foreign_credit:
            line.foreign_credit = new_foreign_credit
        
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
    def _prepare_move_line_residual_amounts(
        self,
        aml_values,
        counterpart_currency,
        shadowed_aml_values=None,
        other_aml_values=None,
    ):
        """Prepare the available residual amounts for each currency.

        RATIONALE FOR OVERRIDING (REAL PORTION IMPLEMENTATION):
        Odoo 17's native method computes the accounting reconciliation rate ('get_accounting_rate')
        by dividing 'amount_currency / balance'. In dual-currency economies with high fluctuation,
        this native approach completely ignores the subtraction adjustments and global mass pricing
        applied to custom control fields ('foreign_debit' and 'foreign_credit'). This mismatch
        leads to phantom exchange rate differences due to rounding errors during reconciliation.

        This override intercepts the calculation when the target currency matches the company's
        foreign currency, forcing Odoo to determine the effective real accounting rate based on
        the pre-balanced Real Portion fields on the move line.
        """

        def is_payment(aml):
            return aml.move_id.payment_id or aml.move_id.statement_line_id

        def get_odoo_rate(aml, other_aml, currency):
            if forced_rate := self._context.get(
                "forced_rate_from_register_payment"
            ):
                return forced_rate
            if other_aml and not is_payment(aml) and is_payment(other_aml):
                return get_accounting_rate(other_aml, currency)
            if aml.move_id.is_invoice(include_receipts=True):
                exchange_rate_date = aml.move_id.invoice_date
            else:
                exchange_rate_date = (
                    aml._get_reconciliation_aml_field_value(
                        "date", shadowed_aml_values
                    )
                )
            return aml.company_currency_id._get_conversion_rate(
                aml.company_currency_id,
                currency,
                aml.company_id,
                exchange_rate_date,
            )

        def get_accounting_rate(aml, currency):
            # --- START REAL PORTION MODIFICATION ---
            # Check if the evaluated currency is the company's secondary/foreign control currency
            if (
                aml.company_id.currency_foreign_id
                and currency == aml.company_id.currency_foreign_id
            ):
                # Extract the real portion balances from local and foreign custom fields
                local_balance = abs(aml.debit - aml.credit)
                foreign_balance = abs(aml.foreign_debit - aml.foreign_credit)

                if (
                    not aml.company_currency_id.is_zero(local_balance)
                    and foreign_balance > 0.0
                ):
                    # Return the real implicit mathematical rate derived from our balanced fields
                    return foreign_balance / local_balance
            # --- END REAL PORTION MODIFICATION ---

            # Native Odoo fallback for any other currencies
            balance = aml._get_reconciliation_aml_field_value(
                "balance", shadowed_aml_values
            )
            amount_currency = aml._get_reconciliation_aml_field_value(
                "amount_currency", shadowed_aml_values
            )
            if not aml.company_currency_id.is_zero(
                balance
            ) and not currency.is_zero(amount_currency):
                return abs(amount_currency / balance)

        aml = aml_values["aml"]
        other_aml = (other_aml_values or {}).get("aml")
        remaining_amount_curr = aml_values["amount_residual_currency"]
        remaining_amount = aml_values["amount_residual"]
        company_currency = aml.company_currency_id
        currency = aml._get_reconciliation_aml_field_value(
            "currency_id", shadowed_aml_values
        )
        account = aml._get_reconciliation_aml_field_value(
            "account_id", shadowed_aml_values
        )
        has_zero_residual = company_currency.is_zero(remaining_amount)
        has_zero_residual_currency = currency.is_zero(remaining_amount_curr)
        is_rec_pay_account = account.account_type in (
            "asset_receivable",
            "liability_payable",
        )

        available_residual_per_currency = {}

        if not has_zero_residual:
            available_residual_per_currency[company_currency] = {
                "residual": remaining_amount,
                "rate": 1,
            }
        if currency != company_currency and not has_zero_residual_currency:
            available_residual_per_currency[currency] = {
                "residual": remaining_amount_curr,
                "rate": get_accounting_rate(aml, currency),
            }

        if (
            currency == company_currency
            and is_rec_pay_account
            and not has_zero_residual
            and counterpart_currency != company_currency
        ):
            rate = get_odoo_rate(aml, other_aml, counterpart_currency)
            residual_in_foreign_curr = counterpart_currency.round(
                remaining_amount * rate
            )
            if not counterpart_currency.is_zero(residual_in_foreign_curr):
                available_residual_per_currency[counterpart_currency] = {
                    "residual": residual_in_foreign_curr,
                    "rate": rate,
                }
        elif (
            currency == counterpart_currency
            and currency != company_currency
            and not has_zero_residual_currency
        ):
            available_residual_per_currency[counterpart_currency] = {
                "residual": remaining_amount_curr,
                "rate": get_accounting_rate(aml, currency),
            }
        return available_residual_per_currency

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

    def write(self, vals):
        old_values = {
            line.id: {
                'foreign_debit': line.foreign_debit,
                'foreign_credit': line.foreign_credit
            } for line in self
        }
        
        
        if self.env.context.get('skip_real_adjustment_flag'):
            return super(AccountMoveLine, self).write(vals)
    
        res = super(AccountMoveLine, self).write(vals)

        if any(f in vals for f in ['balance', 'amount_currency', 'currency_rate']):
            self._apply_real_portion_adjustment()
            
    
        for line in self:
            old_line_data = old_values.get(line.id)
            if old_line_data:
                old_debit = old_line_data['foreign_debit']
                new_debit = line.foreign_debit
                old_credit = old_line_data['foreign_credit']
                new_credit = line.foreign_credit

                if old_debit != new_debit or old_credit != new_credit:
                    if line.id and line.move_id and line.move_id.id:
                        message_parts = []
                        
                        message_parts.append(_("<b>The accounting line has been updated:</b>"))
                        
                        message_parts.append(_("<b>Account:</b> %s") % line.account_id.display_name)
                        
                        if old_debit != new_debit:
                            message_parts.append(_("<b>Foreign Debit Amount:</b> from %s to %s") % (str(old_debit).replace('.', ','), str(new_debit).replace('.', ',')))
                        if old_credit != new_credit:
                            message_parts.append(_("<b>Foreign Credit Amount:</b> from %s to %s") % (str(old_credit).replace('.', ','), str(new_credit).replace('.', ',')))

                        msg_body = "<br/>".join(message_parts)
                        
                        final_body = Markup(msg_body)

                        self.env['mail.message'].create({
                            'body': final_body,
                            'model': line.move_id._name,
                            'res_id': line.move_id.id,
                            'message_type': 'comment',
                            'subtype_id': self.env.ref('mail.mt_note').id,
                            'author_id': self.env.user.partner_id.id,
                        })

        return res
    

    @api.model
    def _prepare_reconciliation_single_partial(self, debit_values, credit_values, shadowed_aml_values=None):
        res = super()._prepare_reconciliation_single_partial(
            debit_values, credit_values, shadowed_aml_values=shadowed_aml_values
        )

        if not res.get('partial_values'):
            return res

        partial_amount = res['partial_values'].get('amount', 0.0)
        debit_aml = debit_values['aml']
        credit_aml = credit_values['aml']
        company_currency = debit_aml.company_currency_id

        has_debit_fb = hasattr(debit_aml, 'foreign_balance') and debit_aml.foreign_balance
        has_credit_fb = hasattr(credit_aml, 'foreign_balance') and credit_aml.foreign_balance

        recon_debit_amount = debit_values.get('amount_residual', 0.0)
        recon_credit_amount = -credit_values.get('amount_residual', 0.0)
        
        compare_amounts = company_currency.compare_amounts(recon_debit_amount, recon_credit_amount)
        debit_fully_matched = compare_amounts <= 0

        if debit_fully_matched:
            if has_debit_fb and debit_aml.balance:
                percent = partial_amount / abs(debit_aml.balance)
                monto_usd = abs(debit_aml.foreign_balance) * percent
                remaining = debit_values.get('foreign_amount_residual', abs(debit_aml.foreign_balance))
                partial_debit_foreign = min(monto_usd, remaining)
            else:
                partial_debit_foreign = 0.0
            
            partial_credit_foreign = partial_debit_foreign
            foreign_amount_final = partial_debit_foreign
        else:
            if has_credit_fb and credit_aml.balance:
                percent = partial_amount / abs(credit_aml.balance)
                monto_usd = abs(credit_aml.foreign_balance) * percent
                remaining = credit_values.get('foreign_amount_residual', abs(credit_aml.foreign_balance))
                partial_credit_foreign = min(monto_usd, remaining)
            else:
                partial_credit_foreign = 0.0
            partial_debit_foreign = partial_credit_foreign
            foreign_amount_final = partial_credit_foreign

        res['partial_values'].update({
            'foreign_amount': foreign_amount_final,
            'debit_foreign_amount_currency': partial_debit_foreign,
            'credit_foreign_amount_currency': partial_credit_foreign,
        })

        
        return res
    

    @api.depends('debit', 'credit', 'amount_currency', 'account_id', 'currency_id', 'company_id',
                 'matched_debit_ids', 'matched_credit_ids','foreign_balance')
    def _compute_amount_residual(self):
        """ Computes the residual amount of a move line from a reconcilable account in the company currency and the line's currency.
            This amount will be 0 for fully reconciled lines or lines from a non-reconcilable account, the original line amount
            for unreconciled lines, and something in-between for partially reconciled lines.
        """
        need_residual_lines = self.filtered(lambda x: x.account_id.reconcile or x.account_id.account_type in ('asset_cash', 'liability_credit_card'))
        # Run the residual amount computation on all lines stored in the db. By
        # using _origin, new records (with a NewId) are excluded and the
        # computation works automagically for virtual onchange records as well.
        stored_lines = need_residual_lines._origin
        amounts_map = {}
        foreign_amounts_map = {}

        if stored_lines:
            self.env['account.partial.reconcile'].flush_model()
            self.env['res.currency'].flush_model(['decimal_places'])

            aml_ids = tuple(stored_lines.ids)
            PartialModel = self.env['account.partial.reconcile']
            has_debit_fa = hasattr(PartialModel, 'debit_foreign_amount_currency')
            has_credit_fa = hasattr(PartialModel, 'credit_foreign_amount_currency')
            debit_field_sql = "SUM(part.debit_foreign_amount_currency)" if has_debit_fa else "0.0"
            credit_field_sql = "SUM(part.credit_foreign_amount_currency)" if has_credit_fa else "0.0"
            self._cr.execute(f'''
                SELECT
                    part.debit_move_id AS line_id,
                    'debit' AS flag,
                    COALESCE(SUM(part.amount), 0.0) AS amount,
                    SUM(part.debit_amount_currency) AS amount_currency,
                    COALESCE({debit_field_sql}, 0.0) AS foreign_amount
                FROM account_partial_reconcile part
                JOIN res_currency curr ON curr.id = part.debit_currency_id
                WHERE part.debit_move_id IN %s
                GROUP BY part.debit_move_id, curr.decimal_places
                UNION ALL
                SELECT
                    part.credit_move_id AS line_id,
                    'credit' AS flag,
                    COALESCE(SUM(part.amount), 0.0) AS amount,
                    SUM(part.credit_amount_currency) AS amount_currency,
                    COALESCE({credit_field_sql}, 0.0) AS foreign_amount
                FROM account_partial_reconcile part
                JOIN res_currency curr ON curr.id = part.credit_currency_id
                WHERE part.credit_move_id IN %s
                GROUP BY part.credit_move_id, curr.decimal_places
            ''', [aml_ids, aml_ids])
            for line_id, flag, amount, amount_currency, foreign_amount in self.env.cr.fetchall():
                amounts_map[(line_id, flag)] = (amount, amount_currency)
                foreign_amounts_map[(line_id, flag)] = foreign_amount
        else:
            amounts_map = {}

        # Lines that can't be reconciled with anything since the account doesn't allow that.
        for line in self - need_residual_lines:
            line.amount_residual = 0.0
            line.amount_residual_currency = 0.0
            line.foreign_amount_residual = 0.0
            line.foreign_amount_residual_currency = 0.0
            line.reconciled = False

        for line in need_residual_lines:
            # Since this part could be call on 'new' records, 'company_currency_id'/'currency_id' could be not set.
            comp_curr = line.company_currency_id or self.env.company.currency_id
            foreign_curr = line.currency_id or comp_curr

            # Retrieve the amounts in both foreign/company currencies. If the record is 'new', the amounts_map is empty.
            debit_amount, debit_amount_currency = amounts_map.get((line._origin.id, 'debit'), (0.0, 0.0))
            credit_amount, credit_amount_currency = amounts_map.get((line._origin.id, 'credit'), (0.0, 0.0))

            debit_foreign = foreign_amounts_map.get((line._origin.id, 'debit'), 0.0)
            credit_foreign = foreign_amounts_map.get((line._origin.id, 'credit'), 0.0)
            # Subtract the values from the account.partial.reconcile to compute the residual amounts.
            residual = line.balance - debit_amount + credit_amount
            residual_currency = line.amount_currency - debit_amount_currency + credit_amount_currency
            
            line.amount_residual = residual
            line.amount_residual_currency = residual_currency
            line.reconciled = (line.amount_residual == 0.0 and line.amount_residual_currency == 0.0)

            line.foreign_amount_residual = line.foreign_balance - debit_foreign + credit_foreign
            line.foreign_amount_residual_currency = line.foreign_amount_residual

    @api.onchange('amount_currency', 'currency_id', 'foreign_inverse_rate')
    def _inverse_amount_currency(self):
        """
        Calcula el balance basándose única y exclusivamente en lo que el usuario digita.
        No mira líneas vecinas ni calcula proporciones globales para evitar bucles.
        """
        comp_curr = self.env.company.currency_id
        for line in self:
            if line.currency_id == comp_curr:
                if line.balance != line.amount_currency:
                    line.balance = line.amount_currency
                continue

            if (
                line.currency_id != comp_curr
                and not line.move_id.is_invoice(True)
                and not self.env.is_protected(self._fields['balance'], line)
            ):
                rate = line.currency_rate or 1.0
                line.balance = line.amount_currency * rate

    
    @api.depends('currency_rate', 'balance')
    def _compute_amount_currency(self):
        """
        Calcula el importe extranjero de forma aislada e independiente en la interfaz.
        Removida la dependencia cruzada 'move_id.line_ids.balance' para matar el bucle cíclico.
        """
        for line in self:
            comp_curr = line.company_id.currency_id
            if line.currency_id == comp_curr:
                line.amount_currency = line.balance
                continue

            rate = line.currency_rate or 1.0
            if line.balance:
                sign = -1.0 if line.balance < 0 else 1.0
                line.amount_currency = sign * (abs(line.balance) / rate if rate else 0.0)
            else:
                line.amount_currency = 0.0

    def _apply_real_portion_adjustment(self):
        if self.env.context.get('skip_real_adjustment_flag'):
            return

        moves_mapped = defaultdict(lambda: self.env['account.move.line'])
        for line in self:
            moves_mapped[line.move_id] |= line

        for move, lines in moves_mapped.items():
            comp_curr = move.company_id.currency_id
            if move.is_invoice(True):
                continue

            foreign_lines = move.line_ids.filtered(
                lambda l: l.currency_id != comp_curr and l.display_type not in ('line_section', 'line_note')
            )

            if len(foreign_lines) <= 2:
                continue

            valid_rates = foreign_lines.filtered(lambda l: l.currency_rate)
            macro_rate = valid_rates[0].currency_rate if valid_rates else 1.0
            if not macro_rate:
                continue

            move_seguro = move.with_context(skip_real_adjustment_flag=True)
            
            total_allocated_balance = 0.0
            last_line = foreign_lines[-1]

            for line in foreign_lines[:-1]:
                sign = -1.0 if line.amount_currency < 0 else 1.0
                line_balance = (abs(line.amount_currency) / macro_rate) * sign
                
                move_seguro.line_ids.filtered(lambda l: l.id == line.id).balance = line_balance
                total_allocated_balance += line_balance

            remaining_balance = -total_allocated_balance
            move_seguro.line_ids.filtered(lambda l: l.id == last_line.id).balance = remaining_balance