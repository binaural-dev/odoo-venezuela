from odoo import fields, models


class AccountTaxInherit(models.Model):
    _inherit = "account.tax"

    # Mismo campo (nombre y semántica) que define l10n_ve_pos_mf: si ambos
    # módulos están instalados, Odoo fusiona la definición sin conflicto.
    fiscal_code = fields.Integer(
        string="Código Fiscal (MF)",
        default=0,
        help="Código para la máquina fiscal TFHKA: 0=Exento, 1=IVA General, "
        "2=IVA Reducido, 3=IVA Adicional",
    )
