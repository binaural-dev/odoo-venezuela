from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_amount

from .product_combo_item import distribute_combo_price, prorate_combo_price


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.constrains('type', 'list_price', 'combo_ids')
    def _check_combo_price_distribution(self):
        self._validate_combo_price_distribution()

    def _validate_combo_price_distribution(self):
        """Simula el reparto con el precio de lista del combo, con todos los
        ítems de cada opción elegidos, y rechaza precios menores o iguales a cero.
        """
        date = fields.Date.context_today(self)
        for template in self.filtered(lambda t: t.type == 'combo' and t.combo_ids):
            currency = template.currency_id or self.env.company.currency_id
            company = template.company_id or self.env.company
            combos = template.sudo().combo_ids
            shares = prorate_combo_price(
                template.list_price,
                [
                    (combo, combo.currency_id._convert(combo.base_price, currency, company, date))
                    for combo in combos
                ],
                currency.round,
            )
            for combo in combos.filtered(lambda c: c.price_distribution == 'by_item_type'):
                entries = []
                for item in combo.combo_item_ids:
                    fixed_price = 0.0
                    if item.item_type == 'fixed_price':
                        fixed_price = item.currency_id._convert(item.lst_price, currency, company, date)
                    entries.append((item, item.item_type, item.percentage, fixed_price))
                prices = distribute_combo_price(shares[combo], entries, currency.round)
                if any(price <= 0 for price in prices.values()):
                    raise ValidationError(_(
                        "Combo \"%(product)s\", option \"%(option)s\": the part of the combo "
                        "price for this option is %(share)s, which is not enough for its fixed "
                        "price and percentage items, so some items would get a zero or "
                        "negative price. Review the prices of the items or the combo price.",
                        product=template.name,
                        option=combo.name,
                        share=format_amount(self.env, shares[combo], currency),
                    ))
