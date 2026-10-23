from odoo import models, fields


class ResPartner(models.Model):
    _inherit = "res.partner"

    withholding_type_id = fields.Many2one(
        "account.withholding.type",
        string="Withholding Type",
        domain=[("state", "=", True)],
        tracking=True,
    )

    iva_account = fields.Many2one(
        "account.account", string="IVA Account"
    )

    islr_account = fields.Many2one(
        "account.account", string="ISLR Account"
    )

    type_person_id = fields.Many2one(
        "type.person", "Type Person", store=True, tracking=True
    )

    economic_activity_id = fields.Many2one(
        "economic.activity", "Default Economic Activity", store=True, tracking=True
    )

    retention_indexation_mode = fields.Selection(
        [
            ("not_indexed", "Non-indexed (invoice rate)"),
            ("indexed", "Indexed"),
        ],
        string="Default retention indexation",
        tracking=True,
        help=(
            "Initial value of the indexation of the retention vouchers of this contact. The voucher"
            " inherits it and it can be changed in the voucher itself. Without a value the voucher"
            " starts non-indexed."
        ),
    )
    use_indexed_retentions = fields.Boolean(compute="_compute_use_indexed_retentions")

    def _compute_use_indexed_retentions(self):
        enabled = self.env.company.use_indexed_retentions
        for partner in self:
            partner.use_indexed_retentions = enabled

    is_current_company_partner = fields.Boolean(
        compute='_compute_is_current_company_partner',
        string="Is Current Company Partner",
    )

    def _compute_is_current_company_partner(self):
        company_partner_ids = self.env['res.company'].search([]).mapped('partner_id.id')        
        for partner in self:
            partner.is_current_company_partner = partner.id in company_partner_ids