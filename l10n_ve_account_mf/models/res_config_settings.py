from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    invoice_print_type = fields.Selection(
        string="Tipo de Impresión de Facturas",
        related="company_id.invoice_print_type",
        readonly=False,
        help="Determina el tipo de impresión predeterminado para facturas de cliente",
    )

    mf_flag_21 = fields.Selection(
        string="Flag 21 - Formato de Números (MF)",
        related="company_id.mf_flag_21",
        readonly=False,
        help="Formato numérico configurado en la impresora fiscal TFHKA (Web Serial).",
    )
