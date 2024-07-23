from odoo import fields, models, _

class MobileSubsidiaryDiary(models.Model):

    _name = "mobile.subsidiary.diary"

    subsidiary_id = fields.Many2one(
        "account.analytic.account",
        string="Subsidiary",
        domain=lambda self: (
            f"[('is_subsidiary', '=', True),('id', 'in', {self.env.user.subsidiary_ids.ids})]"
        ),
        compute="_compute_subsidiary_id",
        store=True,
        readonly=False,
        tracking=True,
    )

    dairy_fiscal = fields.Many2one("account.journal")

    dairy_no_fiscal = fields.Many2one("account.journal")


    @api.depends('company_subsidiary')
    def _compute_subsidiary_id(self):
        for record in self:
            if record.subsidiary_id:
                continue
            record.subsidiary_id = self.env.user.subsidiary_id  if record.company_subsidiary else None

