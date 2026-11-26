import re

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

# Códigos de medio de pago que la máquina fiscal TFHKA reserva para divisas
# (manual HKA V8.5.0). Con el Flag 50 en 00 los rechaza y con 01 cobra el IGTF.
FOREIGN_CURRENCY_FISCAL_CODES = range(20, 25)


def is_foreign_currency_fiscal_code(code):
    """Indica si ``code`` es un código fiscal de divisa (20-24).

    Igual que ``TfhkaDriver._isDivisaPaymentMethod``: solo cuentan los dígitos,
    así que ``"2"`` es el ``02`` y ``" 20"`` es el ``20``.
    """
    digits = re.sub(r"\D", "", code or "")
    return bool(digits) and int(digits) in FOREIGN_CURRENCY_FISCAL_CODES


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    code_fiscal_printer = fields.Char(
        string="Código Fiscal Printer",
        size=2,
        default="01",
        help="Payment method code for the TFHKA fiscal printer (01-24).\n\n"
             "  • 01-19 = Local currency payment methods, without IGTF "
             "(01 = Cash, 02 = Check, 03 = Credit card, 04 = Debit card, "
             "05 = Food voucher, 06 = Bank transfer, 07 = Bank deposit, "
             "08 = Mobile payment).\n"
             "  • 20-24 = Foreign currency payment methods. They require "
             "\"Apply IGTF\" on the payment method: without it, a fiscal "
             "printer with IGTF disabled rejects them and voids the invoice, "
             "and one with IGTF enabled charges an IGTF the PoS did not "
             "charge.\n\n"
             "IMPORTANT: The code must be registered in the fiscal printer."
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = list(super()._load_pos_data_fields(config_id))
        if "code_fiscal_printer" not in fields_list:
            fields_list.append("code_fiscal_printer")
        return fields_list

    @api.constrains(
        # apply_igtf vive en l10n_ve_pos_igtf, del que este módulo no depende:
        # solo se declaran los campos que existan.
        lambda self: [
            name
            for name in ("code_fiscal_printer", "apply_igtf")
            if name in self._fields
        ]
    )
    def _check_foreign_currency_fiscal_code_igtf(self):
        """Un código fiscal de divisa (20-24) exige ``apply_igtf`` activo.

        Sin ``l10n_ve_pos_igtf`` el PdV nunca cobra IGTF, así que ningún
        método puede tener un código de divisa.
        """
        has_igtf_field = "apply_igtf" in self._fields
        for method in self:
            if not is_foreign_currency_fiscal_code(method.code_fiscal_printer):
                continue
            if has_igtf_field and method.apply_igtf:
                continue
            raise ValidationError(
                _(
                    "The payment method “%(method)s” has the fiscal code "
                    "%(code)s, which the fiscal printer reserves for foreign "
                    "currency payments with IGTF. Enable “Apply IGTF” on the "
                    "payment method or use a local currency code (01-19).",
                    method=method.display_name,
                    code=method.code_fiscal_printer,
                )
            )
