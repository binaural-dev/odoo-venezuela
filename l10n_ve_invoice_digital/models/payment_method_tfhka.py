from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class PaymentMethod(models.Model):
    _name = 'payment.method.tfhka'
    _description = 'TFHKA payment methods'
    _rec_name = 'code'
    _order = 'code'

    code = fields.Char(size=2, help="This code identifies the payment method. It is used to digitize and link the corresponding payment method.", required=True, copy=False)
    description = fields.Char(size=100, required=True,)
    
    @api.constrains('code')
    def _check_code(self):
        for record in self:
            code = self.env['payment.method.tfhka'].search([('id', '=', record.code)], limit=1)
            if code:
                raise ValidationError(_("The payment method code already exists"))
            