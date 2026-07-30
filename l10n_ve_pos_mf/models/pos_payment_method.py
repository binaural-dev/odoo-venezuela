from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    code_fiscal_printer = fields.Char(size=2, default="01")

    @api.constrains('code_fiscal_printer', 'apply_igtf')
    def _check_igtf_fiscal_code(self):
        if 'apply_igtf' not in self._fields:
            return
        for record in self:
            if not record.apply_igtf or not record.code_fiscal_printer:
                continue
            if not record.code_fiscal_printer.isdigit() or not (20 <= int(record.code_fiscal_printer) <= 24):
                raise ValidationError(_(
                    "El método de pago '%(name)s' tiene activado IGTF. "
                    "El Código de Impresora Fiscal debe estar entre 20 y 24. "
                    "Valor actual: '%(code)s'.",
                    name=record.name, code=record.code_fiscal_printer,
                ))
