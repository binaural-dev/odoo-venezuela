from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    series_correlative_sequence_id = fields.Many2one("ir.sequence", string="Series control number", tracking=True)
    is_contingency = fields.Boolean(default=False, tracking=True)
