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

    is_current_company_partner = fields.Boolean(
        compute='_compute_is_current_company_partner',
        string="Is Current Company Partner",
    )

    def _compute_is_current_company_partner(self):
        company_partner_ids = self.env['res.company'].search([]).mapped('partner_id.id')        
        for partner in self:
            partner.is_current_company_partner = partner.id in company_partner_ids