from odoo import api, fields, models

class PendingDebtList(models.Model):
    _name = "pending.debt.list"
    _description = "Pending Debt List"

    _sql_constraints = [
        (
            "code_company_uniq_debt",
            "unique (company_id)",
            "La configuración de fecha tope ser unica.",
        ),
    ]

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )

    date_end = fields.Date(string="Date end", help="Date end")
    amount = fields.Float(string="Amount")