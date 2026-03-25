from odoo.tools.float_utils import float_round
from odoo import api, models, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import formatLang

import logging

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _get_tax_totals_summary(
        self, base_lines, currency, company, cash_rounding=None
    ):
        
        
        

        ## Base currency
        res = super()._get_tax_totals_summary(
            base_lines, currency, company, cash_rounding
        )

        #only ves currency
        ves_currency = self.env.ref('base.VEF')
        
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        
        record = False
        if active_model and active_id:
            if isinstance(active_id, api.NewId):
                active_id = active_id.origin
            if active_id:
                record = self.env[active_model].browse(active_id)

        if not record and base_lines:
            try:
                first_line = base_lines[0].get('record')
                if first_line and isinstance(first_line, models.Model):
                    if hasattr(first_line, 'move_id'):
                        record = first_line.move_id
                    elif hasattr(first_line, 'order_id'):
                        record = first_line.order_id
                    else:
                        record = first_line
            except Exception as e:
                _logger.warning("Error deduciendo el record al generar summary tax base %s", e)

        if not record:
            return res
        currency_id = self.env.company.currency_id or False
        foreign_currency_id = self.env.company.foreign_currency_id or False
        company_rate = 1.0
        has_discount= False
        if active_model == "account.move" and record.move_type in ("out_invoice", "in_invoice", "out_refund", "in_refund"):
            company_rate = record.company_currency_rate
            currency_id = record.currency_id
            foreign_currency_id =record.foreign_currency_id
            has_discount = any(
                line.discount > 0
                for line in record.invoice_line_ids
            )
        else: 
            if hasattr(record, 'company_id'): 
                currency_id = record.company_id.currency_id
            else:
                currency_id = self.env.company.currency_id
            foreign_currency_id = self.env.company.foreign_currency_id

        # FIXME: Evaluar escenarios en los que hay descuentos.
        res_without_discount = res.copy()
        #? QUESTION do i need to put the amount without discount?
        
        #total amount discount 
        
        formatted_total_discount = 0.0
        formatted_total_discount_ves = 0.0
        if has_discount:
            exchange_rate = company_rate
            total_discount_amount = sum([
                (line.get("price_unit", 0.0) * line.get("quantity", 0.0) * line.get("discount", 0.0) / 100)
                for line in base_lines
            ])
            total_discount_amount_ves = total_discount_amount * exchange_rate
            formatted_total_discount = formatLang(
                env=self.env,
                value=total_discount_amount,
                currency_obj=currency_id
            )
            #discount only en VEF
            formatted_total_discount_ves = formatLang(
                env=self.env,
                value=total_discount_amount_ves,
                currency_obj=ves_currency
            )
        foreign_lines = []
        #has_discount = not currency.is_zero(sum([line["discount"] for line in base_lines]))
        # if has_discount:
        #     base_without_discount = [line.copy() for line in base_lines if line]
        #     for base_line in base_without_discount:
        #         base_line["discount"] = 0

        #     res_without_discount = super()._get_tax_totals_summary(
        #         base_lines,
        #         currency,
        #         company,
        #         cash_rounding
        #     )
        if record._name == 'account.move':
            foreign_lines, _foreign_tax_lines = record._get_rounded_foreign_base_and_tax_lines()
        elif record._name in ('sale.order','purchase.order'):
            company_id = (self.company_id or self.env.company)
            foreign_lines = [line._prepare_foreign_base_line_for_taxes_computation() for line in record.order_line]
            
            self._add_tax_details_in_base_lines(foreign_lines, company_id)
            self._round_base_lines_tax_details(foreign_lines, company_id)
        foreign_res = super()._get_tax_totals_summary(
            foreign_lines,
            foreign_currency_id,
            company,
            cash_rounding
        )
        #amounts in foreign currency
        res['foreign_currency_id'] = foreign_res['currency_id']
        res['ves_currency_id'] = self.env.ref('base.VEF').id
        res['base_amount_foreign_currency'] = foreign_res['base_amount_currency']
        res['tax_amount_foreign_currency'] = foreign_res['tax_amount_currency']
        res['total_amount_foreign_currency'] = foreign_res['total_amount_currency']
        #discount amount 
        res['formatted_total_discount'] = formatted_total_discount
        res['formatted_total_discount_ves'] = formatted_total_discount_ves
        # Moneda Base
        res['formatted_base_amount_currency'] = formatLang(
            env=self.env,
            value=res.get('base_amount_currency', 0.0),
            currency_obj=currency_id
        )
        res['formatted_tax_amount_currency'] = formatLang(
            env=self.env,
            value=res.get('tax_amount_currency', 0.0),
            currency_obj=currency_id
        )
        res['formatted_total_amount_currency'] = formatLang(
            env=self.env,
            value=res.get('total_amount_currency', 0.0),
            currency_obj=currency_id
        )

        

        #only VES amounts
        res['formatted_base_amount_currency_ves'] = formatLang(
            env=self.env,
            value=res.get('base_amount', 0.0),
            currency_obj=ves_currency
        )
        res['formatted_tax_amount_currency_ves'] = formatLang(
            env=self.env,
            value=res.get('tax_amount', 0.0),
            currency_obj=ves_currency
        )
        res['formatted_total_amount_currency_ves'] = formatLang(
            env=self.env,
            value=res.get('total_amount', 0.0),
            currency_obj=ves_currency
        )
    
        # Foraneos
        res['formatted_base_amount_foreign_currency'] = formatLang(
            env=self.env,
            value=res.get('base_amount_foreign_currency', 0.0),
            currency_obj=foreign_currency_id
        )
        res['formatted_tax_amount_foreign_currency'] = formatLang(
            env=self.env,
            value=res.get('tax_amount_foreign_currency', 0.0),
            currency_obj=foreign_currency_id
        )
        res['formatted_total_amount_foreign_currency'] = formatLang(
            env=self.env,
            value=res.get('total_amount_foreign_currency', 0.0),
            currency_obj=foreign_currency_id
        )

        for res_subtotal, foreign_subtotal in zip(res.get("subtotals", []), foreign_res.get("subtotals", [])):
            res_subtotal["tax_amount_foreign_currency"] = foreign_subtotal.get("tax_amount_currency", 0.0)
            res_subtotal["base_amount_foreign_currency"] = foreign_subtotal.get("base_amount_currency", 0.0)
            res_subtotal["total_amount_foreign_currency"] = foreign_subtotal.get("total_amount_currency", 0.0)

            #Foraneo
            res_subtotal['formatted_base_amount_foreign_currency'] = formatLang(
                env=self.env,
                value=res_subtotal.get('base_amount_foreign_currency', 0.0),
                currency_obj=foreign_currency_id
            )
            res_subtotal['formatted_tax_amount_foreign_currency'] = formatLang(
                env=self.env,
                value=res_subtotal.get('tax_amount_foreign_currency', 0.0),
                currency_obj=foreign_currency_id
            )
            res_subtotal['formatted_total_amount_foreign_currency'] = formatLang(
                env=self.env,
                value=res_subtotal.get('total_amount_foreign_currency', 0.0),
                currency_obj=foreign_currency_id
            )
            #ONLY VES
            res_subtotal['formatted_base_amount_currency_ves'] = formatLang(
                env=self.env,
                value=res_subtotal.get('base_amount', 0.0),
                currency_obj=ves_currency
            )
            res_subtotal['formatted_tax_amount_currency_ves'] = formatLang(
                env=self.env,
                value=res_subtotal.get('tax_amount', 0.0),
                currency_obj=ves_currency
            )
            res_subtotal['formatted_total_amount_currency_ves'] = formatLang(
                env=self.env,
                value=res_subtotal.get('total_amount', 0.0),
                currency_obj=ves_currency
            )
            #Base sistema
            res_subtotal['formatted_base_amount_currency'] = formatLang(
                env=self.env,
                value=res_subtotal.get('base_amount_currency', 0.0),
                currency_obj=currency_id
            )
            res_subtotal['formatted_tax_amount_currency'] = formatLang(
                env=self.env,
                value=res_subtotal.get('tax_amount_currency', 0.0),
                currency_obj=currency_id
            )
            res_subtotal['formatted_total_amount_currency'] = formatLang(
                env=self.env,
                value=res_subtotal.get('total_amount_currency', 0.0),
                currency_obj=currency_id
            )

            #Amount discount
            

            for res_tax_group, foreign_tax_group in zip(res_subtotal.get("tax_groups", []), foreign_subtotal.get("tax_groups", [])):
                res_tax_group["tax_amount_foreign_currency"] = foreign_tax_group.get("tax_amount_currency", 0.0)
                res_tax_group["base_amount_foreign_currency"] = foreign_tax_group.get("base_amount_currency", 0.0)
                res_tax_group["display_base_amount_foreign_currency"] = foreign_tax_group.get("display_base_amount_currency", 0.0)
                # Moneda base
                res_tax_group['formatted_base_amount_currency'] = formatLang(
                    env=self.env,
                    value=res_tax_group.get('base_amount_currency', 0.0),
                    currency_obj=currency_id
                )
                res_tax_group['formatted_tax_amount_currency'] = formatLang(
                    env=self.env,
                    value=res_tax_group.get('tax_amount_currency', 0.0),
                    currency_obj=currency_id
                )
                # Display
                res_tax_group['formatted_display_base_amount_currency'] = formatLang(
                    env=self.env,
                    value=res_tax_group.get('display_base_amount_currency', 0.0),
                    currency_obj=currency_id
                )
                #ONLY VES
                res_tax_group['formatted_base_amount_currency_ves'] = formatLang(
                    env=self.env,
                    value=res_tax_group.get('base_amount', 0.0),
                    currency_obj=ves_currency
                )
                res_tax_group['formatted_tax_amount_currency_ves'] = formatLang(
                    env=self.env,
                    value=res_tax_group.get('tax_amount', 0.0),
                    currency_obj=ves_currency
                )
                res_tax_group['formatted_total_amount_currency_ves'] = formatLang(
                    env=self.env,
                    value=res_tax_group.get('total_amount', 0.0),
                    currency_obj=ves_currency
                )
                # Foranea
                res_tax_group['formatted_base_amount_foreign_currency'] = formatLang(
                    env=self.env,
                    value=res_tax_group.get('base_amount_foreign_currency', 0.0),
                    currency_obj=foreign_currency_id
                )
                res_tax_group['formatted_tax_amount_foreign_currency'] = formatLang(
                    env=self.env,
                    value=res_tax_group.get('tax_amount_foreign_currency', 0.0),
                    currency_obj=foreign_currency_id
                )
                res_tax_group['formatted_display_base_amount_foreign_currency'] = formatLang(
                    env=self.env,
                    value=res_tax_group.get('display_base_amount_foreign_currency', 0.0),
                    currency_obj=foreign_currency_id
                )
        return res
    
    @api.model
    def _prepare_foreign_base_line_for_taxes_computation(self, record, **kwargs):
        """ Convert any representation of a business object ('record') into a base line being a python
        dictionary that will be used to use the generic helpers for the taxes computation.

        The whole method is designed to ease the conversion from a business record.
        For example, when passing either account.move.line, either sale.order.line or purchase.order.line,
        providing explicitely a 'product_id' in kwargs is not necessary since all those records already have
        an `product_id` field.

        :param record:  A representation of a business object a.k.a a record or a dictionary.
        :param kwargs:  The extra values to override some values that will be taken from the record.
        :return:        A dictionary representing a base line.
        """
        def load(field, fallback, from_base_line=False):
            return self._get_base_line_field_value_from_record(record, field, kwargs, fallback, from_base_line=from_base_line)

        currency = (
            load('foreign_currency_id', None)
            or self.env.company.foreign_currency_id)
        base_line = {
            **kwargs,
            'record': record,
            'id': load('id', 0),

            # Basic fields:
            'product_id': load('product_id', self.env['product.product']),
            'product_uom_id': load('product_uom_id', self.env['uom.uom']),
            'tax_ids': load('tax_ids', self.env['account.tax']),
            'price_unit': load('price_unit', 0.0),
            'quantity': load('quantity', 0.0),
            'discount': load('discount', 0.0),
            'currency_id': currency,
            'deferred_start_date': self._get_base_line_field_value_from_record(record, 'deferred_start_date', kwargs, False),
            'deferred_end_date': self._get_base_line_field_value_from_record(record, 'deferred_end_date', kwargs, False),

            # The special_mode for the taxes computation:
            'special_mode': load('special_mode', False, from_base_line=True),

            # A special typing of base line for some custom behavior:
            'special_type': load('special_type', False, from_base_line=True),

            # All computation are managing the foreign currency and the local one.
            'rate': load('rate', 1.0),

            # For all computation that are inferring a base amount in order to reach a total you know in advance, you have to force some
            # base/tax amounts for the computation (E.g. down payment, combo products, global discounts etc).
            'manual_tax_amounts': load('manual_tax_amounts', None, from_base_line=True),
            'manual_total_excluded_currency': load('manual_total_excluded_currency', None, from_base_line=True),
            # Add a function allowing to filter out some taxes during the evaluation. Those taxes can't be removed from the base_line
            'filter_tax_function': load('filter_tax_function', None, from_base_line=True),
            'manual_total_excluded' : load('manual_total_excluded', None, from_base_line=True),
            # ===== Accounting stuff =====
            'sign': load('sign', 1.0),
            'is_refund': load('is_refund', False),
            'tax_tag_invert': load('tax_tag_invert', False),
            'partner_id': load('partner_id', self.env['res.partner']),
            'account_id': load('account_id', self.env['account.account']),
            'analytic_distribution': load('analytic_distribution', None),
        }

        # --- Lógica extra inspirada en la función base ---
        extra_tax_data = self._import_base_line_extra_tax_data(base_line, load('extra_tax_data', {}) or {})
        base_line.update({
            'computation_key': load('computation_key', extra_tax_data.get('computation_key'), from_base_line=True),
            'manual_tax_amounts': load('manual_tax_amounts', extra_tax_data.get('manual_tax_amounts'), from_base_line=True),
        })
        if 'price_unit' in extra_tax_data:
            base_line['price_unit'] = extra_tax_data['price_unit']

        # Propagar valores personalizados del record si es dict
        if record and isinstance(record, dict):
            for k, v in record.items():
                if k.startswith('_') and k not in base_line:
                    base_line[k] = v

        manual_fields = (
            'manual_total_excluded',
            'manual_total_excluded_currency',
            'manual_total_included',
            'manual_total_included_currency',
        )
        for field in manual_fields:
            base_line.setdefault(field, None)
        return base_line
