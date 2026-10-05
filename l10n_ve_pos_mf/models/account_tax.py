# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountTaxInherit(models.Model):
    _inherit = "account.tax"

    fiscal_code = fields.Integer(
        string="Código Fiscal (MF)",
        default=0,
        help="Código para la máquina fiscal TFHKA: 0=Exento, 1=IVA General, 2=IVA Reducido, 3=IVA Adicional"
    )
