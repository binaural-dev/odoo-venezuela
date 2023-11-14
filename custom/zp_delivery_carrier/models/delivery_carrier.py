import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    def default_alternate_currency(self):
        """
        This method is used to get the foreign currency of the company and set it as the default
        value of the foreign currency field.

        Returns
        -------
        type = int
            The id of the foreign currency of the company
        """
        return self.env.company.currency_foreign_id.id or False

    date_rate = fields.Date()
    foreign_currency_id = fields.Many2one(
        "res.currency",
        default=default_alternate_currency,
    )
    foreign_rate = fields.Float(
        help="The foreign rate used to calculate delivery costs.",
        # compute="_compute_rate",
        related='foreign_currency_id.rate',
        digits="Tasa",
        default=0.0,
        # store=True,
        # readonly=False,
    )
    foreign_inverse_rate = fields.Float(
        help="The rate used as a factor to multiply the foreign currency.",
        compute="_compute_rate",
        digits=(16, 15),
        default=0.0,
        store=True,
    )

    def _update_currency_date(self, date: fields.Date):
        """Updates the ``date_rate`` of the shipment method.

        Parameters
        ----------
        date : fields.Date
            The date you want to set.
        """
        self.ensure_one()
        if date != fields.Date.context_today(self):
            date = fields.Date.context_today(self)

        if not self.date_rate or date != self.date_rate:
            self.date_rate = date

    @api.depends("create_date", "date_rate")
    def _compute_rate(self):
        Rate = self.env["res.currency.rate"]
        date_rate = self.date_rate or fields.Date.context_today(self)
        for delivery in self:
            foreign_currency_id = delivery.foreign_currency_id.id

            rate = Rate.compute_rate(foreign_currency_id, date_rate)
            delivery.update(rate)

    def rate_shipment(self, order):
        ''' Compute the price of the order shipment

        :param order: record of sale.order
        :return dict: {'success': boolean,
                       'price': a float,
                       'error_message': a string containing an error message,
                       'warning_message': a string containing a warning message}
                       # TODO maybe the currency code?
        '''
        self.ensure_one()
        self._update_currency_date(order.date_order.date())

        return super().rate_shipment(order)


class DeliveryGrip(models.Model):
    _inherit = "delivery.carrier"

    def _get_extra_charge_per_kg(self, line, price, weight):
        order_weight = weight * 0.1 + weight
        kg_apply_extra = line.kg_apply_extra
        kg_extra_charge = line.kg_extra_charge # self.delivery_kg_extra_charge
        kg_extra_charge_amount = line.kg_extra_charge_amount # self.delivery_kg_extra_charge_amount
        extra_price_per_weight = 0

        if 0 in [kg_extra_charge, kg_extra_charge_amount] and kg_apply_extra:
            return price

        extra_price_per_weight = int(order_weight / kg_extra_charge) * kg_extra_charge_amount

        return price + extra_price_per_weight

    def _get_price_from_picking(self, total, weight, volume, quantity):
        price = 0.0
        criteria_found = False
        price_dict = self._get_price_dict(total, weight, volume, quantity)
        if self.free_over and total >= self.amount:
            return 0
        for line in self.price_rule_ids:
            test = safe_eval(line.variable + line.operator + str(line.max_value), price_dict)
            if test:
                price = line.list_base_price + line.list_price * price_dict[line.variable_factor]
                price = self._get_extra_charge_per_kg(line, price, weight)
                criteria_found = True
        if not criteria_found:
            raise UserError(_("No price rule matching this order; delivery cost cannot be computed."))

        return price