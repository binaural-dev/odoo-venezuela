from odoo import api, models, fields, _
from odoo.tools.sql import column_exists, create_column
from odoo.exceptions import UserError

class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_igtf = fields.Boolean(string="Is a IGTF journal?", default=False, tracking=True)

    @api.onchange('is_igtf','currency_id')
    def _onchange_is_igtf(self):
        if self.is_igtf and self.currency_id == self.env.ref("base.VEF"):
            raise UserError(_("The IGTF journal cannot have VEF as currency. Please select another currency."))