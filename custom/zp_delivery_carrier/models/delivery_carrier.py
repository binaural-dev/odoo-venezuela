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
        compute="_compute_rate",
        digits="Tasa",
        default=0.0,
        store=True,
        readonly=False,
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
