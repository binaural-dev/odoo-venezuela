from datetime import timedelta

from odoo import fields, models


class ResCurrency(models.Model):
    _inherit = "res.currency"

    def _get_rates(self, company, date):
        """Use the rate dated ``date`` for conversions on ``date``, as in Odoo 19.

        Odoo 20 takes the last rate strictly before the date, so a rate dated D only applies from
        D + 1. In Venezuela the BCV rate of a day applies on that same day, and ``compute_rate``
        reads the rate of the exact date. Asking the core for the next day turns its strict
        comparison into "on or before ``date``".
        """
        return super()._get_rates(company, fields.Date.to_date(date) + timedelta(days=1))
