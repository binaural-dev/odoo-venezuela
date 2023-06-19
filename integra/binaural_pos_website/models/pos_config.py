from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    only_website = fields.Boolean()
    team_sale_website_id = fields.Many2one(
        "crm.team", "Team Website", compute="_compute_team_sale_website_id"
    )

    @api.depends("team_sale_website_id")
    def _compute_team_sale_website_id(self):
        for record in self:
            record.team_sale_website_id = self.env.ref("sales_team.salesteam_website_sales").id
