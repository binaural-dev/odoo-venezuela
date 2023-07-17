from odoo import api, fields, models

class PaymentCondition(models.Model):
    _name = "sale.payment.condition"
    _description = 'Payment Condition'

    name = fields.Char(
        string = "Name", 
        required = True
    )