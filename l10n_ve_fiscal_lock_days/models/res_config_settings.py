from odoo import fields, models, _, api


class ResConfigSettingsInherit(models.TransientModel):
    _inherit = "res.config.settings"

    tax_period = fields.Selection(
        [
            ("biweekly", "Quincenal"),
            ("monthly", "Mensual"),
        ],
        string="Periodo de Impuestos Venezuela",
        related="company_id.tax_period",
        readonly=False,
    )
    lock_date_tax_validation = fields.Boolean(
        string="Validación para Bloquear creación de facturas",
        related="company_id.lock_date_tax_validation",
        readonly=False,
    )
