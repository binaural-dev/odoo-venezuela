from odoo import models, api, fields

class AccountAsset(models.Model):
    _inherit = "account.asset"

    def set_to_close(self, invoice_line_ids, date=None, message=None):
        if message:
            self = self.with_context(disposal_message=message)
        return super(AccountAsset, self).set_to_close(invoice_line_ids, date=date, message=message)

    def _get_disposal_moves(self, invoice_lines_list, disposal_date):
        move_ids = super(AccountAsset, self)._get_disposal_moves(invoice_lines_list, disposal_date)
        message = self.env.context.get('disposal_message')
        if message and move_ids:
            moves = self.env['account.move'].browse(move_ids)
            for move in moves:
                move.write({
                    'ref': message,
                })
                move.line_ids.write({
                    'name': message,
                })
        return move_ids
