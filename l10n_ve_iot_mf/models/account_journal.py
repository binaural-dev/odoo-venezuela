from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    payment_method = fields.Char(size=2, default="01")

    @api.constrains('payment_method', 'is_igtf')
    def _check_igtf_payment_method(self):
        if 'is_igtf' not in self._fields:
            return
        for record in self:
            if not record.is_igtf or not record.payment_method:
                continue
            if not record.payment_method.isdigit() or not (20 <= int(record.payment_method) <= 24):
                raise ValidationError(_(
                    "El diario '%(name)s' tiene activado IGTF. "
                    "El Método de Pago Fiscal debe estar entre 20 y 24. "
                    "Valor actual: '%(code)s'.",
                    name=record.name, code=record.payment_method,
                ))
