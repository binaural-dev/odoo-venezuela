from odoo import models, fields
class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    username_tfhka = fields.Char(related="company_id.username_tfhka", string="Username", readonly=False)
    password_tfhka = fields.Char(related="company_id.password_tfhka", string="Password", readonly=False)
    url_tfhka = fields.Char(related="company_id.url_tfhka", string="URL", readonly=False)
    token_auth_tfhka = fields.Char(related="company_id.token_auth_tfhka", string="Token Auth", readonly=False)
    range_assignment_tfhka = fields.Integer(related="company_id.range_assignment_tfhka", string="Range Assignment", readonly=False)
    
    def action_generate_token_tfhka(self):
        self.company_id.generate_token_tfhka()