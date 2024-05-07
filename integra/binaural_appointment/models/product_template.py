from odoo import api, fields, models, _

class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_appointment = fields.Boolean("Is_appointment", default=False)

    time_limit = fields.Float(
        string='Time Limit (hours)',
    )
    
    block_appointment = fields.Integer(
        string='Block Appointment',
    )