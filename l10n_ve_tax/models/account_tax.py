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
        foreign_currency = self.env.company.foreign_currency_id or False
        if not foreign_currency:
            raise ValidationError(_("No foreign currency configured in the company"))

       
   
        ## Base currency
        res = super()._get_tax_totals_summary(
            base_lines, currency, company, cash_rounding
        )
        invoice = self.env['account.move'].search([])
        # FIXME: Evaluar escenarios en los que hay descuentos.
        res_without_discount = res.copy()
        has_discount = not currency.is_zero(sum([line["discount"] for line in base_lines]))
        if has_discount:
            base_without_discount = [line.copy() for line in base_lines if line]
            for base_line in base_without_discount:
                base_line["discount"] = 0

            res_without_discount = super()._get_tax_totals_summary(
                base_lines,
                currency,
                company,
                cash_rounding
            )
        
        foreign_lines,_foreign_tax_lines = invoice._get_rounded_foreign_base_and_tax_lines()
        foreign_res = super()._get_tax_totals_summary(
            foreign_lines,
            foreign_currency,
            company,
            cash_rounding
        )
        res['foreign_currency_id'] = foreign_res['currency_id']
        res['base_amount_foreign_currency'] = foreign_res['base_amount_currency']
        res['tax_amount_foreign_currency'] = foreign_res['tax_amount_currency']
        res['total_amount_foreign_currency'] = foreign_res['total_amount_currency']

        for res_subtotal, foreign_subtotal in zip(res.get("subtotals", []), foreign_res.get("subtotals", [])):
            res_subtotal["tax_amount_foreign_currency"] = foreign_subtotal.get("tax_amount_currency", 0.0)
            res_subtotal["base_amount_foreign_currency"] = foreign_subtotal.get("base_amount_currency", 0.0)
            res_subtotal["total_amount_foreign_currency"] = foreign_subtotal.get("total_amount_currency", 0.0)

            for res_tax_group, foreign_tax_group in zip(res_subtotal.get("tax_groups", []), foreign_subtotal.get("tax_groups", [])):
                res_tax_group["tax_amount_foreign_currency"] = foreign_tax_group.get("tax_amount_currency", 0.0)
                res_tax_group["base_amount_foreign_currency"] = foreign_tax_group.get("base_amount_currency", 0.0)
                res_tax_group["display_base_amount_foreign_currency"] = foreign_tax_group.get("display_base_amount_currency", 0.0)
        _logger.warning("res %s", res)
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
            or load('company_id', self.env['res.company'].foreign_currency_id)
        )

        return {
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

            # The special_mode for the taxes computation:
            # - False for the normal behavior.
            # - total_included to force all taxes to be price included.
            # - total_excluded to force all taxes to be price excluded.
            'special_mode': load('special_mode', False, from_base_line=True),

            # A special typing of base line for some custom behavior:
            # - False for the normal behavior.
            # - early_payment if the base line represent an early payment in mixed mode.
            # - cash_rounding if the base line is a delta to round the business object for the cash rounding feature.
            'special_type': load('special_type', False, from_base_line=True),

            # All computation are managing the foreign currency and the local one.
            # This is the rate to be applied when generating the tax details (see '_add_tax_details_in_base_line').
            'rate': load('rate', 1.0),

            # For all computation that are inferring a base amount in order to reach a total you know in advance, you have to force some
            # base/tax amounts for the computation (E.g. down payment, combo products, global discounts etc).
            'manual_tax_amounts': load('manual_tax_amounts', None, from_base_line=True),

            # Add a function allowing to filter out some taxes during the evaluation. Those taxes can't be removed from the base_line
            # when dealing with group of taxes to maintain a correct link between the child tax and its parent.
            'filter_tax_function': load('filter_tax_function', None, from_base_line=True),

            # ===== Accounting stuff =====

            # The sign of the business object regarding its accounting balance.
            'sign': load('sign', 1.0),

            # If the document is a refund or not to know which repartition lines must be used.
            'is_refund': load('is_refund', False),

            # If the tags must be inverted or not.
            'tax_tag_invert': load('tax_tag_invert', False),

            # Extra fields for tax lines generation:
            'partner_id': load('partner_id', self.env['res.partner']),
            'account_id': load('account_id', self.env['account.account']),
            'analytic_distribution': load('analytic_distribution', None),
        }
