from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    create_invoice_after_validate_out = fields.Boolean()


