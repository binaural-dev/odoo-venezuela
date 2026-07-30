# -*- coding: utf-8 -*-
from odoo import api, models, fields


class AccountTaxInherit(models.Model):
    _inherit = "account.tax"

    fiscal_code = fields.Integer(
        string="Código Fiscal (MF)",
        default=0,
        help="Código para la máquina fiscal TFHKA: 0=Exento, 1=IVA General, 2=IVA Reducido, 3=IVA Adicional"
    )

    @api.model
    def _load_pos_data_fields(self, config):
        fields_list = list(super()._load_pos_data_fields(config))
        if "fiscal_code" not in fields_list:
            fields_list.append("fiscal_code")
        return fields_list
