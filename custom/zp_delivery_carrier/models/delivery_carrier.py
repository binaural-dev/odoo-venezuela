import logging

from odoo import _, api, fields, models

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

    def get_order_weight(self, order):
        for record in order:
            weight = 0
            for line in record.order_line:
                weight += line.product_id.weight * line.product_uom_qty

            weight = weight * 0.1 + weight
            record.shipping_amount_weight = weight

    def _get_additional_cost_per_kg(self, price, order):
        order_weight = self.get_order_weight(order)
        delivery_kg_extra_charge_divisor = self.company.delivery_kg_extra_charge_divisor
        delivery_kg_extra_charge_amount = self.company.delivery_kg_extra_charge_amount

        extra_cost_per_weight = int(order_weight / delivery_kg_extra_charge_divisor) * delivery_kg_extra_charge_amount

        return price + extra_cost_per_weight

    def pre_rate_shipment(self, order):
        ''' Compute the price of the order shipment

        :param order: record of sale.order
        :return dict: {'success': boolean,
                       'price': a float,
                       'error_message': a string containing an error message,
                       'warning_message': a string containing a warning message}
                       # TODO maybe the currency code?
        '''
        self.ensure_one()

        if hasattr(self, '%s_rate_shipment' % self.delivery_type):
            res = getattr(self, '%s_rate_shipment' % self.delivery_type)(order)

            _logger.warning('------pre_rate_shipment---------pre_rate_shipment------')
            _logger.warning(res)
            _logger.warning('---------------------')
            # apply fiscal position
            company = self.company_id or order.company_id or self.env.company
            res['price'] = self.product_id._get_tax_included_unit_price(
                company,
                company.currency_id,
                order.date_order,
                'sale',
                fiscal_position=order.fiscal_position_id,
                product_price_unit=res['price'],
                product_currency=company.currency_id
            )
            # apply margin on computed price
            res['price'] = float(res['price']) * (1.0 + (self.margin / 100.0))

            res['price'] = res['price']
            # save the real price in case a free_over rule overide it to 0
            res['carrier_price'] = self._get_additional_cost_per_kg(res['price'])
            # free when order is large enough
            amount_without_delivery = order._compute_amount_total_without_delivery()
            if res['success'] and self.free_over and self._compute_currency(order, amount_without_delivery, 'pricelist_to_company') >= self.amount:
                res['warning_message'] = _('The shipping is free since the order amount exceeds %.2f.') % (self.amount)
                res['price'] = 0.0
            return res


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

        return self.pre_rate_shipment(order)
