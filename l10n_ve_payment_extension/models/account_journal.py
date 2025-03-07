from odoo import api, fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    default_account_id = fields.Many2one(
        domain=(
            "[('deprecated', '=', False), ('company_id', '=', company_id),"
            "'|',('account_type', '=', default_account_type),"
            "('account_type', 'in', ('asset_current', 'liability_current'))]"
        )
    )
