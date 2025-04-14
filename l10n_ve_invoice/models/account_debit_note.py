from odoo import api, models

class AccountDebitNote(models.TransientModel):
    _inherit = 'account.debit.note'
    

    @api.onchange('journal_type')
    def _onchange_journal_filter_by_config(self):

        config = self.env['ir.config_parameter'].sudo()
        filter_enabled = config.get_param('account.move.auto_select_debit_note_journal') == 'True'

        if filter_enabled:
            nd_journal = self.env['account.journal'].search([('code', '=', 'ND')], limit=1)
            if nd_journal:
                self.journal_id = nd_journal.id
          