from odoo import api, models, fields


class ResPartner(models.Model):
    _inherit = "res.partner"

    taxpayer_type = fields.Selection(
        [
            ("formal", "Formal"),
            ("special", "Special"),
            ("ordinary", "Ordinary"),
        ],
        default="ordinary",
        tracking=True,
        store=True,
    )
    is_foreign_partner = fields.Boolean(
        compute="_compute_is_foreign_partner",
        string="Is Foreign Partner",
    )

    def _is_company_partner(self):
        """True if the partner belongs to a company of the database. It works
        over virtual records (NewId) because it only uses _origin."""
        self.ensure_one()
        company_partner_ids = self.env["res.company"].sudo().search([]).partner_id.ids
        return self._origin.id in company_partner_ids

    def _is_foreign_partner(self):
        """A foreign partner is any contact (customer, supplier or other) whose
        country is not Venezuela. The partner of any company of the database is
        never considered foreign.
        """
        self.ensure_one()
        if not self.country_id or self.country_id.code == "VE":
            return False
        return not self._is_company_partner()

    @api.depends("country_id")
    def _compute_is_foreign_partner(self):
        for partner in self:
            partner.is_foreign_partner = partner._is_foreign_partner()
