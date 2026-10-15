from odoo import api, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _load_pos_self_data_fields(self, config):
        """Expone ``fiscal_code`` al cliente del Kiosko.

        Es el código fiscal del impuesto que la TFHKA usa por línea
        (0=Exento, 1=General, 2=Reducido, 3=Adicional). ``account.tax`` ya se
        carga en el dataset del Kiosko; solo faltaba el campo.
        """
        fields_list = list(super()._load_pos_self_data_fields(config))
        if "fiscal_code" not in fields_list:
            fields_list.append("fiscal_code")
        return fields_list
