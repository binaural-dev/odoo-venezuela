from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    invoice_print_type = fields.Selection(
        string="Tipo de Impresión de Facturas",
        related="company_id.invoice_print_type",
        readonly=False,
        help="Determina el tipo de impresión predeterminado para facturas de cliente",
    )
