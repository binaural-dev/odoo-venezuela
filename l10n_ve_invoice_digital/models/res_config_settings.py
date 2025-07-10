from odoo import models, fields
class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    username_tfhka = fields.Char(related="company_id.username_tfhka", string="Username", readonly=False)
    password_tfhka = fields.Char(related="company_id.password_tfhka", string="Password", readonly=False)
    url_tfhka = fields.Char(related="company_id.url_tfhka", string="URL", readonly=False)
    token_auth_tfhka = fields.Char(related="company_id.token_auth_tfhka", string="Token Auth", readonly=False)
<<<<<<< HEAD
    range_assignment_tfhka = fields.Integer(related="company_id.range_assignment_tfhka", string="Range Assignment", readonly=False)
    
=======
    invoice_digital_tfhka = fields.Boolean(related="company_id.invoice_digital_tfhka", string="Invoice Digital", readonly=False)
    sequence_validation_tfhka = fields.Boolean(related="company_id.sequence_validation_tfhka", string="Sequence Validation", readonly=False)

>>>>>>> 710f656381dbee1faec49a534a47c6a7ef5b7282
    def action_generate_token_tfhka(self):
        self.company_id.generate_token_tfhka()