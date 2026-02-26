from odoo import api, models, fields, _
from odoo.exceptions import UserError

class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_igtf = fields.Boolean(string="Is a IGTF journal?", default=False, tracking=True)

    @api.onchange('is_igtf', 'currency_id')
    def _check_igtf_currency(self):
        for journal in self:

            if journal.is_igtf and journal.currency_id and journal.currency_id == self.env.ref("base.VEF"):
                raise UserError(_(
                        "IGTF journals require a foreign currency."
                    ))
            elif not journal.currency_id and journal.is_igtf:
                raise UserError(_(
                        "A journal marked as IGTF must have a foreign currency assigned."
                    ))