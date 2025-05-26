from odoo import api, models,fields

class AccountDebitNote(models.TransientModel):
    _inherit = 'account.debit.note'
    filter_enabled = fields.Boolean(string='Filter Enabled', compute='_compute_filter_enabled')
    
    @api.depends('journal_type')
    def _compute_filter_enabled(self):
        move = self.env['account.move'].browse(self.env.context.get('active_id'))
        config = move.company_id.auto_select_debit_note_journal
        for record in self:
            record.filter_enabled = config