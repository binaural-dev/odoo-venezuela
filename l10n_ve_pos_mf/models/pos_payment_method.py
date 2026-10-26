from odoo import fields, models, api, _


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
