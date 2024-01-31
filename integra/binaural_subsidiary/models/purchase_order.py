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
        readonly=False
    )

    company_subsidiary = fields.Boolean(
        related='company_id.subsidiary'
    )

    @api.depends('company_subsidiary')
    def _compute_account_analytic_id(self):
        for record in self:
            record.account_analytic_id = self.env.user.subsidiary_id  if record.company_subsidiary else None
