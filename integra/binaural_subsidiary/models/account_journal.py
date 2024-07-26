from odoo import _, api, fields, models


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
