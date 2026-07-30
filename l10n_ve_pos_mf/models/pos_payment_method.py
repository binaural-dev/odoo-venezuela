from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    code_fiscal_printer = fields.Char(
        string="Código Fiscal Printer",
        size=2,
        default="01",
        help="Código del método de pago para la máquina fiscal TFHKA (01-24).\n\n"
             "Valores comunes:\n"
             "  • 01 = Efectivo\n"
             "  • 02 = Cheque\n"
             "  • 03 = Tarjeta de Crédito\n"
             "  • 04 = Tarjeta de Débito\n"
             "  • 05 = Vale de Alimentos (Ticket)\n"
             "  • 06 = Transferencia Bancaria\n"
             "  • 07 = Depósito Bancario\n"
             "  • 08 = Pago Móvil\n"
             "  • 09-24 = Métodos personalizados\n\n"
             "IMPORTANTE: Este código debe estar registrado en la impresora fiscal."
    )

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
