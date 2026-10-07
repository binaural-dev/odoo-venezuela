from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


def distribute_combo_price(combo_price, entries, round_amount):
    """Reparte el precio de un combo entre sus ítems según el item_type.

    `entries` es una lista ordenada de (clave, item_type, percentage, fixed_price);
    devuelve {clave: precio}. El último principal (o la última entrada si no
    hay principal) absorbe el residuo de redondeo.
    """
    prices = {}
    for key, item_type, _pct, fixed_price in entries:
        if item_type == 'fixed_price':
            prices[key] = round_amount(fixed_price)

    remain_after_fixed = combo_price - sum(prices.values())

    total_percentage = 0.0
    for key, item_type, pct, _fixed in entries:
        if item_type == 'percentage':
            amount = round_amount(remain_after_fixed * (pct / 100.0))
            prices[key] = amount
            total_percentage += amount

    remain_for_principal = remain_after_fixed - total_percentage
    principals = [key for key, item_type, _p, _f in entries if item_type == 'principal']
    if principals:
        average = round_amount(remain_for_principal / len(principals))
        for key in principals:
            prices[key] = average
        delta = combo_price - sum(prices.values())
        if delta:
            prices[principals[-1]] += delta
    elif entries:
        delta = combo_price - sum(prices.values())
        if delta:
            last = entries[-1][0]
            prices[last] = prices.get(last, 0.0) + delta
    return prices


def prorate_combo_price(combo_price, base_prices, round_amount):
    """Prorratea el precio del combo entre sus opciones (misma regla del core).

    `base_prices` es una lista ordenada de (opción, base_price); devuelve
    {opción: parte}. Sin base_price reparte en partes iguales; el residuo de
    redondeo va a la última opción.
    """
    total = sum(base for _key, base in base_prices)
    if total:
        shares = {key: round_amount(base * combo_price / total) for key, base in base_prices}
    else:
        even = round_amount(combo_price / len(base_prices))
        shares = {key: even for key, _base in base_prices}
    delta = combo_price - sum(shares.values())
    if delta:
        shares[base_prices[-1][0]] += delta
    return shares


class ProductComboItem(models.Model):
    _inherit = 'product.combo.item'

    item_type = fields.Selection(
        selection=[
            ('principal', 'Principal'),
            ('percentage', 'Percentage'),
            ('fixed_price', 'Fixed Price'),
        ],
        string="Item Type",
        required=True,
        default="principal",
        help=(
            "Principal: gets what is left of the option's price after the fixed "
            "price and percentage items; several principal items split it equally.\n"
            "Percentage: gets the given % of what is left after the fixed price "
            "items.\n"
            "Fixed Price: keeps the price of its product, which must be greater "
            "than 0."
        ),
    )

    percentage = fields.Float(
        string="Percentage (%)",
        digits=(16, 2),
        default=0.0,
    )

    @api.constrains('item_type', 'percentage')
    def _check_percentage_value(self):
        for item in self:
            if item.item_type == 'percentage' and (item.percentage < 0 or item.percentage > 100):
                raise ValidationError(_("The percentage for the item must be between 0 and 100."))

    @api.constrains('item_type', 'product_id', 'combo_id')
    def _check_fixed_price_value(self):
        for item in self:
            if (
                item.combo_id.price_distribution == 'by_item_type'
                and item.item_type == 'fixed_price'
                and item.lst_price <= 0
            ):
                raise ValidationError(_(
                    "The product of a fixed price item must have a price greater than 0."
                ))

    @api.constrains('item_type', 'percentage', 'product_id')
    def _check_price_distribution_of_combo_products(self):
        self.env['product.template'].sudo().search(
            [('combo_ids', 'in', self.combo_id.ids)]
        )._validate_combo_price_distribution()

