from odoo import api, fields, models, _

class ResCompany(models.Model):
    _inherit = "res.company"

    advance_customer_account_id = fields.Many2one(
        "account.account",
        string="Advance Customer Account",
        domain = [('deprecated', '=', False)],
        help="Account used for advance payments from customers",
    )

    advance_supplier_account_id = fields.Many2one(
        "account.account",
        string="Advance Supplier Account",
        domain = [('deprecated', '=', False)],
        help="Account used for advance payments to suppliers",
    )