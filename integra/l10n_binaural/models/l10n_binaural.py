from odoo import models, fields


class L10nBinaural(models.Model):
    _inherit = "account.chart.template"

    journal_ids = fields.One2many("account.journal", "template_id", string="Journals")
