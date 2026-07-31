from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    invoice_print_type = fields.Selection(
        selection=[("free", "Forma Libre"), ("fiscal", "Máquina Fiscal")],
        string="Tipo de Impresión de Factura",
        default="free",
    )

    mf_flag_21 = fields.Selection(
        selection=[
            ("00", "00 - Estándar (8+2 enteros, 5+3 cantidad)"),
            ("01", "01 - Precisión decimal (7+3 enteros, 5+3 cantidad)"),
            ("02", "02 - Alta precisión (6+4 enteros, 5+3 cantidad)"),
            ("30", "30 - Montos grandes (14+2 enteros, 14+3 cantidad)"),
        ],
        string="Flag 21 - Formato de Números (MF)",
        default="00",
        help="Formato numérico configurado en la impresora fiscal TFHKA. "
        "Usado por la impresión fiscal Web Serial desde Facturación/Contabilidad.",
    )
