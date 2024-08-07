from odoo import fields, models


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _create_payment(self, **extra_create_values):
        """
        Inherits the original method so the payment is created with the rate of the current date.
        """
        Rate = self.env["res.currency.rate"]

        rate_values = Rate.compute_rate(self.company_id.currency_foreign_id.id, fields.Date.today())
        return super()._create_payment(**extra_create_values | rate_values)
