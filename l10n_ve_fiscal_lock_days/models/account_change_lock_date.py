from odoo import models, fields, _
from odoo.exceptions import ValidationError 

from datetime import timedelta


class AccountChangeLockDate(models.TransientModel):
    """
    This wizard is used to change the lock date
    """

    _inherit = "account.change.lock.date"

    def change_lock_date(self):
        res = super(AccountChangeLockDate, self).change_lock_date()
        if self.tax_lock_date:
            adjusted_lock_date = self.tax_lock_date + timedelta(days=1)
            sale_orders = self.env["sale.order"].search(
                [
                    ("invoice_status", "=", "to invoice"),
                    ("date_order", "<", adjusted_lock_date),
                ]
            )
            if sale_orders:
                raise ValidationError(
                    _(
                        "You cannot set the lock date to %s because there are sales orders in 'To Invoice' status with an order date prior to this."
                    )
                    % self.tax_lock_date
                )
        return res
