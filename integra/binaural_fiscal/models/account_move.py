from odoo import fields, models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    fiscal = fields.Boolean(related='journal_id.fiscal', store=True)
