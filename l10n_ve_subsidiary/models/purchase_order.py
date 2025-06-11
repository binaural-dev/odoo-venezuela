from odoo import _, api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _default_subsidiary_id(self):
        subsidiary = self.env.user.subsidiary_id.id if self.env.company.subsidiary else False
        return subsidiary

    account_analytic_id = fields.Many2one(
        "account.analytic.account",
        string="Subsidiary",
        domain=lambda self: (
            f"[('is_subsidiary', '=', True),('id', 'in', {self.env.user.subsidiary_ids.ids})]"
        ),
        default=_default_subsidiary_id,
        store=True,
        readonly=False,
        tracking=True,
    )

    company_subsidiary = fields.Boolean(
        related='company_id.subsidiary', string="Company Subsidiary",
    )
    
    suitable_journal_ids = fields.Many2many(
        comodel_name='account.journal',
        compute='_compute_suitable_journal_ids'
    )

    journal_invoice_id = fields.Many2one(
        "account.journal", string="Journal Invoice", domain="[('type', '=', 'purchase')]"
    )

    @api.depends('company_id', 'account_analytic_id')
    def _compute_suitable_journal_ids(self):
        """
        Get all journals having at least one payment method for inbound/outbound depending on the payment_type.
        """
        domain = [
            ('company_id', 'in', self.company_id.ids),
            ('type', '=', 'purchase')
        ]

        get_domain_subsidiaries_suitable_journals = self.env["account.journal"].get_domain_subsidiaries_suitable_journals

        for record in self:
            domain = get_domain_subsidiaries_suitable_journals(domain, record.account_analytic_id.id)
            record.suitable_journal_ids = self.env["account.journal"].search(domain)
    
    @api.constrains('account_analytic_id', 'journal_invoice_id')
    def _constraint_change_subsidiary_id(self):
        for record in self:
            if not record.journal_invoice_id:
                continue
            record.journal_invoice_id.check_journal_selected(record.account_analytic_id.id)