from odoo import api, fields, models, _


class AccountJournal(models.Model):
    _inherit = "account.journal"

    ref_length_required = fields.Integer(string="Ref length required", default=0)
    ref_required = fields.Boolean(related="company_id.ref_required")
