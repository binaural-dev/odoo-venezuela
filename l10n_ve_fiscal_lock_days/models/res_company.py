from odoo import fields, models, api
import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    tax_period = fields.Selection(
        [
            ("biweekly", "Quincenal"),
            ("monthly", "Mensual"),
        ],
        string="Periodo de Impuestos Venezuela",
    )

    lock_date_tax_validation = fields.Boolean(
        string="Validación para Bloquear creación de facturas"
    )
