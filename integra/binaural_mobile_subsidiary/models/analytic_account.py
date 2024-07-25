from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression


class AccountAnalitycAccount(models.Model):
    _inherit = "account.analytic.account"

    selectable_sale_journal_ids = fields.Many2many(
        comodel_name='account.journal',
        compute='_compute_selectable_sale_journal_ids'
    )

    dairy_fiscal = fields.Many2one(
        "account.journal",
    )
    dairy_no_fiscal = fields.Many2one(
        "account.journal"
    )

    def _compute_selectable_sale_journal_ids(self):
        """
        Get all journals having at least one payment method for inbound/outbound depending on the payment_type.
        """
        domain = [
            ('company_id', 'in', self.company_id.ids),
            ('type', '=', 'sale')
        ]

        domain = expression.AND([domain, ['|', ('subsidiary_id', '=', self.id), ('subsidiary_id', '=', False)]])

        journals = self.env['account.journal'].search(domain)
        
        for record in self:
            record.selectable_sale_journal_ids = journals
