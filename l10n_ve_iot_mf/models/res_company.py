import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"
    
    invoice_print_type = fields.Selection(
        selection=[
            ('free', 'Forma Libre'),
            ('fiscal', 'Máquina Fiscal')
        ],
        string='Tipo de Impresión de Factura',
        default='free'
    )    