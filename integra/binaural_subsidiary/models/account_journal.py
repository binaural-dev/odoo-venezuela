from odoo import _, api, fields, models
from odoo.osv import expression

import logging
_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = "account.journal"

    subsidiary_id = fields.Many2one(
        "account.analytic.account",
        string="Subsidiary",
        domain=lambda self: (
            f"[('is_subsidiary', '=', True),('id', 'in', {self.env.user.subsidiary_ids.ids})]"
        ),
        default=lambda self: self.env.user.subsidiary_id,
        compute="_compute_subsidiary_id",
        store=True,
        readonly=False,
        tracking=True,
    )

    company_subsidiary = fields.Boolean(
        related='company_id.subsidiary', store=True, string="Company Subsidiary",
    )

    @api.depends('company_subsidiary')
    def _compute_subsidiary_id(self):
        for record in self:
            if record.subsidiary_id:
                continue
            record.subsidiary_id = self.env.user.subsidiary_id  if record.company_subsidiary else None


    @api.model
    def get_domain_subsidiaries_suitable_journals(self, domain, record_parent_subsidiary_id = None):

        if not record_parent_subsidiary_id:
            domain = expression.AND(
            [
                domain, 
                [
                    '|', ('subsidiary_id', 'in', self.env.user.subsidiary_ids.ids), ('subsidiary_id', '=', False)
                ]
            ])

            return domain
    
        domain = expression.AND(
            [
                domain, 
                [
                    '|', ('subsidiary_id', '=', record_parent_subsidiary_id), ('subsidiary_id', '=', False)
                ]
            ]
        )

        return domain
