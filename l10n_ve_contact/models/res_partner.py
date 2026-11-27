import logging
import re
from collections import Counter
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

    def _default_prefix_vat(self):
        """Default of the form: a new company (default_is_company, e.g. from the
        Customers action) is J. On save the default is fixed by
        _add_missing_default_values from the record itself."""
        return "J" if self.env.context.get("default_is_company") else "V"

    @api.model
    def _add_missing_default_values(self, values):
        """The action context (default_is_company) also reaches the contacts
        created from the form of a company, which are persons and have no prefix
        field in their dialog. When no prefix is given, the default follows the
        is_company of the record that is being created, not the context."""
        prefix_given = "prefix_vat" in values
        values = super()._add_missing_default_values(values)
        if not prefix_given and "prefix_vat" in values:
            values["prefix_vat"] = "J" if values.get("is_company") else "V"
        return values

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
        default=_default_prefix_vat,
        help="Prefix of the VAT number",
        tracking=True,
    )

    allowed_prefix_vat = fields.Json(
        compute="_compute_allowed_prefix_vat",
        string="Allowed Prefix VAT",
    )

    def _is_own_company_partner(self):
        """True if the partner is the one of a company of the database. Its
        literal is free: a company can be a legal entity (J) or a sole
        proprietorship of a person (V)."""
        self.ensure_one()
        company_partner_ids = self.env["res.company"].sudo().search([]).partner_id.ids
        return self._origin.id in company_partner_ids

    def _get_allowed_prefix_vat(self):
        """A company is J (legal), G (government) or C (communal); a person is V
        (Venezuelan), E (foreigner) or P (passport). A contact that belongs to a
        company has its own fiscal data: it does not follow its parent."""
        self.ensure_one()
        if self._is_own_company_partner():
            return ["V", "E", "J", "G", "P", "C"]
        if self.is_company:
            return ["J", "G", "C"]
        return ["V", "E", "P"]

    @api.depends("is_company")
    def _compute_allowed_prefix_vat(self):
        for partner in self:
            partner.allowed_prefix_vat = partner._get_allowed_prefix_vat()

    @api.onchange("is_company")
    def _onchange_is_company_prefix_vat(self):
        for partner in self:
            if partner.prefix_vat not in partner.allowed_prefix_vat:
                partner.prefix_vat = partner.allowed_prefix_vat[0]

    @api.constrains("prefix_vat", "is_company", "vat")
    def _check_prefix_vat_by_contact_type(self):
        """Task 87829: the literal of the RIF must match the contact type. A
        partner without number is not checked yet."""
        for partner in self:
            if not partner.vat or not partner.prefix_vat:
                continue
            allowed = partner._get_allowed_prefix_vat()
            if partner.prefix_vat not in allowed:
                raise ValidationError(
                    _(
                        "The prefix %(prefix)s is not valid for %(name)s: use %(allowed)s.",
                        prefix=partner.prefix_vat,
                        name=partner.display_name,
                        allowed=", ".join(allowed),
                    )
                )

    @api.constrains("name")
    def _check_name_immutable(self):
        if not self.env.company.validate_partner_name_immutable:
            return

        if self.env.user.has_group(
            "l10n_ve_contact.group_edit_partner_name_immutable"
        ):
            return

        model_checks = {
            "sale.order": [("partner_id", "=", "id")],
            "purchase.order": [("partner_id", "=", "id")],
            "account.move": [
                ("partner_id", "=", "id"),
                ("move_type", "in", ["out_invoice", "in_invoice"]),
            ],
            "account.move.line": [("partner_id", "=", "id")],
        }

        for partner in self:
            for model, domain in model_checks.items():
                if model not in self.env.registry.models:
                    continue
                # Replace 'id' placeholder with actual partner.id
                resolved_domain = [
                    (field, op, partner.id if val == "id" else val)
                    for field, op, val in domain
                ]
                if self.env[model].search_count(resolved_domain) > 0:
                    raise ValidationError(
                        _(
                            "You cannot modify the name of a contact with associated "
                            "transactions."
                        )
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
            else:
                 error_message = _(
                    "There is already a partner with the same VAT number for this company."
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
            if "email" in vals and vals.get("type", "contact") == "contact":
                self.check_duplicate_email(vals.get("email"))
        partners = super(ResPartner, self).create(vals_list)
        # The check above only sees partners already in the database, so two
        # contacts of the same batch (an import) with the same email let each
        # other in. Once created they can see each other. Only contacts are
        # counted: an address of the batch sharing a contact's email doesn't
        # trigger the check.
        batch_emails = Counter(
            partner.email for partner in partners
            if partner.type == "contact" and partner.email
        )
        for partner in partners:
            if partner.type == "contact" and batch_emails[partner.email] > 1:
                partner.check_duplicate_email(partner.email)
        return partners

    def write(self, vals):
        # Only the contacts whose email really changes are checked: writing back
        # the email a contact already has (e.g. a form, an import or any process
        # that sends every field) must not fail because another partner shares it.
        email_changed = self.browse()
        if "email" in vals:
            email_changed = self.filtered(lambda partner: partner.email != vals["email"])
        res = super().write(vals)
        if "prefix_vat" and "vat" in vals:
            for record in self:
                record.check_duplicate_vat(
                    vals.get("prefix_vat"), vals.get("vat"))
        if "email" in vals:
            for record in email_changed:
                if record.type == "contact":
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
    