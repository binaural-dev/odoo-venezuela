from odoo import api, models


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    @api.model
    def _load_pos_self_data_fields(self, config):
        """Expone ``code_fiscal_printer`` al cliente del Kiosko.

        Es el código de 2 dígitos que la máquina fiscal TFHKA asocia a cada
        forma de pago (``payment_lines`` del comprobante). ``l10n_ve_pos_mf`` lo
        expone en el loader de caja; aquí se hace lo propio para el Kiosko.
        """
        fields_list = list(super()._load_pos_self_data_fields(config))
        if "code_fiscal_printer" not in fields_list:
            fields_list.append("code_fiscal_printer")
        return fields_list
