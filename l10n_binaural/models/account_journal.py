from odoo import models, fields


class L10nBinauralAccountJournal(models.Model):
    _inherit = "account.journal"

    template_id = fields.Many2one("chart.account.template", string="Template", ondelete="restrict")
