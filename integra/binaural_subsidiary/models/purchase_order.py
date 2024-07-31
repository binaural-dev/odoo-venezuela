from odoo import _, api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    account_analytic_id = fields.Many2one(
        "account.analytic.account",
        string="Subsidiary",
        domain=lambda self: (
            f"[('is_subsidiary', '=', True),('id', 'in', {self.env.user.subsidiary_ids.ids})]"
        ),
        compute="_compute_account_analytic_id",
        store=True,
        readonly=False,
        tracking=True,
    )

    company_subsidiary = fields.Boolean(
        related='company_id.subsidiary', store=True, string="Company Subsidiary",
    )
    
    suitable_journal_ids = fields.Many2many(
        comodel_name='account.journal',
        compute='_compute_suitable_journal_ids'
    )

    @api.depends('company_subsidiary')
    def _compute_account_analytic_id(self):
        for record in self:
            if record.account_analytic_id:
                continue
            record.account_analytic_id = self.env.user.subsidiary_id  if record.company_subsidiary else None

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
