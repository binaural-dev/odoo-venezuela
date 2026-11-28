from odoo import fields, models, api, _


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    code_fiscal_printer = fields.Char(
        string="Código Fiscal Printer",
        size=2,
        default="01",
        help="Código del método de pago para la máquina fiscal TFHKA (01-24). "
             "Es el de los pagos en la moneda de la caja y el de las monedas que "
             "no tienen su propio código en la configuración por moneda.\n\n"
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

    def _get_fiscal_code(self, currency=None):
        """Fiscal printer code of a payment made with this method in
        ``currency``: the one of the method and currency settings when it has
        one, the code of the method otherwise."""
        self.ensure_one()
        setting = self._get_currency_settings(currency) if currency else False
        return (setting and setting.code_fiscal_printer) or self.code_fiscal_printer or False

    @api.model
    def _load_pos_data_fields(self, config):
        fields_list = list(super()._load_pos_data_fields(config))
        if fields_list and "code_fiscal_printer" not in fields_list:
            fields_list.append("code_fiscal_printer")
        return fields_list
