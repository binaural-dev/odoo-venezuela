from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    batchs_journal_id = fields.Many2one("account.journal", domain=[("type", "=", "sale")])
