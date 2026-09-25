from odoo import models, fields, api, _

import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    validate_user_creation_by_company = fields.Boolean(
        default = False,
        string='Validate user creation by company',
    )
    
    validate_user_creation_general = fields.Boolean(
        default = False,
        string='Validate user creation general',
    )

    validate_partner_name_immutable = fields.Boolean(
        default=True,
        string="Prevent renaming contacts with transactions",
    )

    prefix_vat = fields.Selection(
        related="partner_id.prefix_vat",
        string="Prefix VAT",
        readonly=False,
        store=True,
        help="Literal (V/E/J/G/P/C) of the company's own RIF. Not set "
        "automatically on company creation -- must be confirmed here so "
        "reports that print the company's RIF (retention voucher, ARCV, "
        "SENIAT filings) show the correct literal instead of the Selection "
        "field's default.",
    )


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            partner = self.env["res.partner"].create(
                {
                    "name": vals["name"],
                    "is_company": False,
                    "image_1920": vals.get("logo"),
                    "email": vals.get("email"),
                    "phone": vals.get("phone"),
                    "website": vals.get("website"),
                    "vat": vals.get("vat"),
                    "country_id": vals.get("country_id"),
                }
            )
            partner.company_id = False
            vals["partner_id"] = partner.id
        return super().create(vals_list)
