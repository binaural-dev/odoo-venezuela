from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError
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
    def get_domain_subsidiaries_suitable_journals(self, domain, id_record_parent_subsidiary = None):

        if not id_record_parent_subsidiary:
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
                    '|', ('subsidiary_id', '=', id_record_parent_subsidiary), ('subsidiary_id', '=', False)
                ]
            ]
        )

        return domain

    def check_journal_selected(self, account_analytic_id):
        if self.subsidiary_id.id == account_analytic_id.id:
            return

        raise UserError(
            _(
                "The subsidiary of either journal and record must be the same",
            )
        )