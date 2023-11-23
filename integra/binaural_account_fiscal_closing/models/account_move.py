# Copyright 2016 Tecnativa - Antonio Espinosa
# Copyright 2017 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models,api
from odoo.exceptions import UserError


class AccountMoveFiscalClosing(models.Model):
    _inherit = 'account.move'

    def _selection_closing_type(self):
        """Use selection values from move_type field in closing config
        (making a copy for preventing side effects), plus an extra value for
        non-closing moves."""
        res = list(
            self.env['account.fiscalyear.closing.config'].fields_get(
                allfields=['move_type']
            )['move_type']['selection']
        )
        res.append(('none', _('None')))
        return res

    fyc_id = fields.Many2one(
        comodel_name='account.fiscalyear.closing', delete="cascade",
        string="Fiscal year close", readonly=True,
    )
    closing_type = fields.Selection(
        selection=_selection_closing_type, default="none",
        states={'posted': [('readonly', True)]},
    )

    # @api.model
    # def create(self, vals):
    #     #print("estoy en el vals del accounting fiscal closing",vals)
    #     #total_debit = sum([x[2]['debit'] for x in vals['line_ids']])
    #     #total_credit = sum([x[2]['credit'] for x in vals['line_ids']])
    #     #print("esto es justo antes de hacer el asiento este es el debit----------:",total_debit)
    #     #print("esto es justo antes de hacer el asiento este es el credit----------:",total_credit)
    #     move = super(AccountMoveFiscalClosing, self.with_context(check_move_validity=False, partner_id=vals.get('partner_id'))).create(vals)
    #     return move

    # #@api.multi
    # def assert_balanced(self):
        # print("assert balance heredado para debug")
        # if not self.ids:
        #     return True
        # prec = self.env['decimal.precision'].precision_get('Account')

        # self._cr.execute("""\
        #     SELECT      move_id
        #     FROM        account_move_line
        #     WHERE       move_id in %s
        #     GROUP BY    move_id
        #     HAVING      abs(sum(debit) - sum(credit)) > %s
        #     """, (tuple(self.ids), 10 ** (-max(4, prec))))
        # if len(self._cr.fetchall()) != 0:
        #     raise UserError(_("Cannot create unbalanced journal entry."))
        # return True