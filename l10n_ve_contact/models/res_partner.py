import logging
import re
from odoo import models, fields, api, _
from odoo.exceptions import MissingError, ValidationError
from ...tools import binaural_cne_query

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    name = fields.Char(tracking=True)

    mobile = fields.Char(tracking=True)

    property_supplier_payment_term_id = fields.Many2one(tracking=True)

    property_payment_term_id = fields.Many2one(tracking=True)

    property_product_pricelist = fields.Many2one(tracking=True)

    property_account_position_id = fields.Many2one(tracking=True)

    street = fields.Char(tracking=True)

    street2 = fields.Char(tracking=True)

    country_id = fields.Many2one(tracking=True, default= lambda self: self.env.ref("base.ve"))

    state_id = fields.Many2one(tracking=True)

    city_id = fields.Many2one(tracking=True)

    municipality = fields.Many2one(tracking=True)
    
    parish_id = fields.Many2one(tracking=True)

    zip = fields.Char(tracking=True)

    def _default_company_id(self):
        company_id = self.env.company.id
        return company_id

    prefix_vat = fields.Selection(
        [
            ("V", "V"),
            ("E", "E"),
            ("J", "J"),
            ("G", "G"),
            ("P", "P"),
            ("C", "C"),
        ],
        string="Prefix VAT",
        default="V",
        help="Prefix of the VAT number",
        tracking=True,
    )

    def check_duplicate_vat(self, prefix_vat, vat, company_id=None):
        error_message = ""
        domain = [
            ("prefix_vat", "=", prefix_vat),
            ("vat", "=", vat),
            ("id", "!=", self.id if self else False),
        ]

        if prefix_vat and vat:
            if self.env.company.validate_user_creation_by_company:
                domain.extend(
                    [
                        ("company_id", "=", company_id or self.env.company.id),
                    ]
                )
                error_message = _(
                    "There is already a partner with the same VAT number for this company."
                )
            elif self.env.company.validate_user_creation_general:
                error_message = _(
                    "A partner with the same VAT number already exists for this company."
                )

            existing_partner = self.env["res.partner"].search(domain)
            if existing_partner:
                raise ValidationError(error_message)

    def check_duplicate_email(self, email, company_id=None):
        if email:
            domain = [
                ("email", "=", email),
                ("id", "!=", self.id if self else False),
            ]

            if self.env.company.validate_user_creation_by_company:
                domain.extend(
                    [
                        ("company_id", "=", company_id or self.env.company.id),
                    ]
                )
                error_message = _(
                    "A partner with the same email address already exists for this company."
                )
            elif self.env.company.validate_user_creation_general:
                error_message = _(
                    "A partner with the same email already exists.")
            else:
                error_message = _(
                    "A partner with the same email address already exists for this company."
                )

            existing_partner = self.env["res.partner"].search(domain, limit=1)
            if existing_partner:
                raise ValidationError(error_message)

    company_id = fields.Many2one(
        default=_default_company_id,
    )

    @api.model_create_multi
    def create(self, vals_list):
        """This function assign the name of the person by the vat number and the prefix of the vat number
        calling the function get_default_name_by_vat from binaural_cne_query before create the partner

        Args:
            prefix_vat (string): prefix of the vat number (V)
            vat (string): vat number of the person, this number is unique in Venezuela

        Raises:
            UserError: Error to connect with CNE, please check your internet connection or try again later

        """
        for vals in vals_list:
            if vals.get("vat") and not vals.get("name", False):
                prefix_vat = vals.get("prefix_vat")
                name = vals.get("name")
                vat = vals.get("vat")
                if prefix_vat == "V" and not name and prefix_vat in ["V", "E"]:
                    name, flag = binaural_cne_query.get_default_name_by_vat(
                        self, prefix_vat, vat
                    )
                    if not flag:
                        continue
                    vals["name"] = name
            if "vat" and "prefix_vat" in vals:
                self.check_duplicate_vat(
                    vals.get("prefix_vat"), vals.get("vat"))
            if "email" in vals:
                self.check_duplicate_email(vals.get("email"))
        return super(ResPartner, self).create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if "prefix_vat" and "vat" in vals:
            for record in self:
                record.check_duplicate_vat(
                    vals.get("prefix_vat"), vals.get("vat"))
        if "email" in vals:
            for record in self:
                record.check_duplicate_email(vals.get("email"))
        return res

    def _check_vat(self):
        pattern = "^[0-9]*$"
        for record in self:
            if record.vat:
                if not re.match(pattern, record.vat):
                    raise MissingError(_("The vat field only accepts numbers"))

    @api.onchange("vat", "prefix_vat")
    def _onchange_(self):
        """This function assign the name of the person by the vat number and the prefix of the vat number
        calling the function get_default_name_by_vat from binaural_cne_query
    
        Args:
            prefix_vat (string): prefix of the vat number (V)
            vat (string): vat number of the person, this number is unique in Venezuela
        """
        if self.vat and not self.name and self.prefix_vat in ["V", "E"]:
            self._check_vat()
            name, flag = binaural_cne_query.get_default_name_by_vat(self, self.prefix_vat, self.vat)
            if not flag:
                return
            for record in self:
                record.name = name
    