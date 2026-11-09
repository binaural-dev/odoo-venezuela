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
    is_foreign_supplier = fields.Boolean(
        compute="_compute_is_foreign_supplier",
        string="Is Foreign Supplier",
    )

    def _is_foreign_supplier(self):
        """A foreign supplier is a supplier whose country is not Venezuela.
        The partner of any company of the database is never considered foreign.
        It works over virtual records (NewId) because it only uses _origin.
        """
        self.ensure_one()
        if not self.country_id or self.country_id.code == "VE":
            return False
        if self.supplier_rank <= 0:
            return False
        company_partner_ids = self.env["res.company"].sudo().search([]).partner_id.ids
        return self._origin.id not in company_partner_ids

    @api.depends("country_id", "supplier_rank")
    def _compute_is_foreign_supplier(self):
        for partner in self:
            partner.is_foreign_supplier = partner._is_foreign_supplier()
