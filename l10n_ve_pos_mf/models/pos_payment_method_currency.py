from odoo import api, fields, models


class PosPaymentMethodCurrency(models.Model):
    _inherit = "pos.payment.method.currency"

    code_fiscal_printer = fields.Char(
        string="Código Fiscal Printer",
        size=2,
        help="Código de la máquina fiscal TFHKA (01-24) de los pagos hechos en "
        "esta moneda con este método. Vacío: se usa el código del método.",
    )

    @api.model
    def _load_pos_data_fields(self, config):
        fields_list = list(super()._load_pos_data_fields(config))
        if "code_fiscal_printer" not in fields_list:
            fields_list.append("code_fiscal_printer")
        return fields_list
