from odoo import models, fields, _
from odoo.exceptions import UserError

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
                raise UserError(
                    _(
                        "No puedes establecer la fecha de bloqueo en %s porque existen pedidos de venta en estado 'Por facturar' con una fecha de orden anterior."
                    )
                    % self.tax_lock_date
                )
        return res
