from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import format_date


class PaymentDateCheckMixin(models.AbstractModel):
    """Single place for the "a payment cannot be dated after today" rule
    (ticket #15682), shared by `account.payment` and
    `account.payment.register`."""

    _name = "l10n_ve.payment.date.check.mixin"
    _description = "Payment future date check"

    def _l10n_ve_allows_future_payment_date(self):
        """Hook: return True to exempt the records in `self` from the rule
        (e.g. a controlled exception for post-dated payments)."""
        return False

    def _l10n_ve_check_payment_date_not_in_future(self, date_field):
        """Raise if the `date_field` of any record in `self` is later than
        today in the user's timezone (`context_today`, never UTC)."""
        today = fields.Date.context_today(self)
        for record in self:
            value = record[date_field]
            if not value or value <= today or record._l10n_ve_allows_future_payment_date():
                continue
            raise ValidationError(
                _(
                    "The payment date (%(date)s) cannot be later than today (%(today)s).",
                    date=format_date(self.env, value),
                    today=format_date(self.env, today),
                )
            )
