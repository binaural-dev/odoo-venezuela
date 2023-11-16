from odoo import api, fields, models

class PendingDebtList(models.Model):
    _name = "pending.debt.list"
    _description = "Pending Debt List"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )

    date_end = fields.Date(string="Date end", help="Date end")
    amount = fields.Float(string="Amount")