from odoo import api, models,fields

class AccountDebitNote(models.TransientModel):
    _inherit = 'account.debit.note'
    filter_enabled = fields.Boolean(string='Filter Enabled', compute='_compute_filter_enabled')
    
    @api.depends('journal_type')
    def _compute_filter_enabled(self):
        config = self.env['ir.config_parameter'].sudo()
        for record in self:
            record.filter_enabled = config.get_param('account.move.auto_select_debit_note_journal') == 'True'