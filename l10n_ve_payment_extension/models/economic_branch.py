from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError


class EconomicBranch(models.Model):
    _name = "economic.branch"
    _rec_name = "name"
    _description = "Economic Branch"
    _sql_constraints = [
        (
            "name_uniq",
            "unique (name,company_id)",
            "You may not register an economic sector with the same name for the selected company.",
        )
    ]

    name = fields.Char(required=True, store=True)
    status = fields.Selection(
        selection=[("active", "Active"), ("inactive", "Inactive")],
        default="active",
        store=True
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    @api.onchange("name")
    def on_change_name(self):
        self.name = str(self.name or "").upper().strip()

    @api.constrains("name", "company_id")
    def _constraint_name_economic_branch(self):
        for record in self:
            exist = self.search(
                [
                    ("name", "=", record.name),
                    ("id", "!=", record.id),
                    ("company_id", "=", record.company_id.id),
                ]
            )

            if any(exist):
                raise ValidationError(_("The economic branch is already registered"))
