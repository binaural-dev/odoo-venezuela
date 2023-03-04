from odoo import api, models, fields, _


class SignatureConfig(models.Model):
    _name = "signature.config"
    _description = "Signature and e-mail configuration "
    _rec_name = "email"
    _check_company_auto = True

    email = fields.Char()
    signature = fields.Binary()
    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
