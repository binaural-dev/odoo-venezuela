from odoo import api, fields, models, _, Command

import logging

_logger = logging.getLogger(__name__)
class AppointmentType(models.Model):
    _inherit = "appointment.type"

    product_id = fields.Many2one(
        "product.product",
        string="Related Product",
        domain="[('is_appointment', '=', True),('sale_ok', '=', True)]",
        required=True,
    )

    prefix_vat = fields.Selection(
        [
            ("V", "V"),
            ("E", "E"),
            ("J", "J"),
            ("G", "G"),
            ("P", "P"),
            ("C", "C"),
        ],
        string="Prefix VAT",
        default="V",
        help="Prefix of the VAT number",
    )

    vat = fields.Char(
        string="Tax ID",
        index=True,
        help="The Tax Identification Number. Values here will be validated based on the country format. You can use '/' to indicate that the partner is not subject to tax.",
    )

    time_limit = fields.Float(
        string='Time Limit (hours)',
        related='product_id.time_limit'
    )
    
    block_appointment = fields.Integer(
        string='Block Appointment',
        related='product_id.block_appointment'
    )