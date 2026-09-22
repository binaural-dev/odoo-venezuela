from odoo import models, fields, api, _
from odoo.exceptions import UserError

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

    prefix_vat_confirmed = fields.Boolean(
        related="partner_id.prefix_vat_confirmed",
        string="Prefix VAT confirmed",
        readonly=False,
        store=True,
        help="Whether prefix_vat above was explicitly reviewed, as opposed "
        "to sitting on the Selection field's untouched 'V' default. Fiscal "
        "documents that print the company's RIF (retention voucher, "
        "SENIAT/ISLR/municipal filings, ARCV) refuse to generate while "
        "this is False.",
    )

    def _check_prefix_vat_confirmed_for_fiscal_documents(self):
        """Raise if this company's RIF literal (prefix_vat) was never
        confirmed. Called from every retention-document entry point
        (comprobante, TXT SENIAT, XLSM ISLR, XLSX municipal, ARCV) instead
        of silently emitting a document with an unconfirmed literal --
        prefix_vat defaults to 'V', so an unconfirmed value looks like a
        real RIF instead of a missing one."""
        for company in self:
            if not company.prefix_vat_confirmed:
                raise UserError(_(
                    "El literal del RIF (%(vat)s) de %(company)s no ha sido "
                    "confirmado -- por defecto puede estar mostrando 'V' sin "
                    "que nadie lo haya revisado. Vaya a Contabilidad > "
                    "Configuración > Compañías, confirme el literal correcto "
                    "(J/V/E/G/P/C) y marque 'Prefix VAT confirmed' antes de "
                    "emitir este documento."
                ) % {"vat": company.vat or "", "company": company.display_name})


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
