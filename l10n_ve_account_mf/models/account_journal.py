from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    payment_method = fields.Char(
        size=2,
        default="01",
        string="Método de Pago (MF)",
        help="Código del método de pago para la máquina fiscal TFHKA (01-24). "
        "01-19 = moneda nacional, 20-24 = divisas (IGTF).",
    )
