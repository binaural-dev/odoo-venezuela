from odoo import api, models, fields, _


class EconomicActivity(models.Model):
    _name = "economic.activity"
    _description = "Economic Activity"
    _sql_constraints = [
        (
            "code_uniq",
            "unique (name,municipality_id)",
            "There cannot be two records with the same code for the selected municipality.",
        ),
        ("aliquot_mayor_cero", "check (aliquot > 0)", "The aliquot must be greater than zero"),
    ]

    name = fields.Char("Code", required=True, store=True)
    municipality_id = fields.Many2one(
        "res.country.municipality", string="Municipality", required=True
    )
    branch_id = fields.Many2one(
        "economic.branch",
        string="Economic branch",
        required=True,
        domain="[('status','=','active')]",
    )
    aliquot = fields.Float(required=True)
    description = fields.Text(required=True)
    minimum_monthly = fields.Float(string="Monthly Taxable Minimum", required=True)
    minimum_annual = fields.Float(string="Annual Taxable Minimum", required=True)

    def _compute_display_name(self):
        for activity in self:
            activity.display_name = (activity.name or "") + " - " + (activity.branch_id.name or "")+ " - " + (activity.municipality_id.name or "")


