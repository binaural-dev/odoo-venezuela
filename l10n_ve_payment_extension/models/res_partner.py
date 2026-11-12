from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


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

    is_resident_person = fields.Boolean(
        compute="_compute_is_resident_person",
        string="Is Resident Person",
    )

    def _get_type_persons_by_xmlid(self, xmlids):
        persons = self.env["type.person"]
        for xmlid in xmlids:
            persons |= (
                self.env.ref(f"l10n_ve_payment_extension.{xmlid}", raise_if_not_found=False)
                or persons
            )
        return persons

    def _get_resident_type_persons(self):
        """Venezuelan person types: PN Residente, PJ Domiciliada and PJ Empresa
        Emisora de Radio Domiciliada. Those are the ones whose taxpayer type
        decides whether the withholding type is required."""
        return self._get_type_persons_by_xmlid(
            (
                "type_person_l10n_ve_payment_extension",
                "type_person_three_l10n_ve_payment_extension",
                "type_person_seven_l10n_ve_payment_extension",
            )
        )

    def _get_non_resident_type_persons(self):
        """Foreign person types: PN No Residente, PJ No Domiciliada,
        Instituciones Financieras No Domiciliadas and Otras PJ No Domiciliada."""
        return self._get_type_persons_by_xmlid(
            (
                "type_person_two_l10n_ve_payment_extension",
                "type_person_four_l10n_ve_payment_extension",
                "type_person_five_l10n_ve_payment_extension",
                "type_person_six_l10n_ve_payment_extension",
            )
        )

    @api.depends("type_person_id")
    def _compute_is_resident_person(self):
        resident_persons = self._get_resident_type_persons()
        for partner in self:
            partner.is_resident_person = bool(
                partner.type_person_id and partner.type_person_id in resident_persons
            )

    def _is_foreign_partner(self):
        """When the person type is one of the Venezuelan ones the partner is not
        foreign, and when it is one of the non-resident ones it is, whatever its
        country. Any other case (no person type, or a custom one) is decided by
        the country, as in l10n_ve_tax_payer."""
        self.ensure_one()
        if self.type_person_id in self._get_resident_type_persons():
            return False
        if self.type_person_id in self._get_non_resident_type_persons():
            return not self._is_company_partner()
        return super()._is_foreign_partner()

    @api.depends("type_person_id")
    def _compute_is_foreign_partner(self):
        # Only adds type_person_id to the dependencies of l10n_ve_tax_payer.
        super()._compute_is_foreign_partner()

    allowed_type_person_ids = fields.Many2many(
        "type.person",
        compute="_compute_allowed_type_person_ids",
        string="Allowed Type Persons",
    )
    is_non_resident_person = fields.Boolean(
        compute="_compute_is_non_resident_person",
        string="Is Non Resident Person",
    )

    def _get_allowed_type_persons(self):
        """Ticket 86944: a person can only be PN Residente or PN No Residente;
        every other type is a legal entity (PJ) and belongs to a company."""
        self.ensure_one()
        if self.is_company:
            return self._get_type_persons_by_xmlid(
                (
                    "type_person_three_l10n_ve_payment_extension",
                    "type_person_four_l10n_ve_payment_extension",
                    "type_person_five_l10n_ve_payment_extension",
                    "type_person_six_l10n_ve_payment_extension",
                    "type_person_seven_l10n_ve_payment_extension",
                )
            )
        return self._get_type_persons_by_xmlid(
            (
                "type_person_l10n_ve_payment_extension",
                "type_person_two_l10n_ve_payment_extension",
            )
        )

    @api.depends("is_company")
    def _compute_allowed_type_person_ids(self):
        for partner in self:
            partner.allowed_type_person_ids = partner._get_allowed_type_persons()

    @api.depends("type_person_id")
    def _compute_is_non_resident_person(self):
        non_resident_persons = self._get_non_resident_type_persons()
        for partner in self:
            partner.is_non_resident_person = bool(
                partner.type_person_id
                and partner.type_person_id in non_resident_persons
                and not partner._is_company_partner()
            )

    @api.onchange("is_company")
    def _onchange_is_company_type_person(self):
        for partner in self:
            if (
                partner.type_person_id
                and partner.type_person_id not in partner._get_allowed_type_persons()
            ):
                partner.type_person_id = False

    @api.onchange("type_person_id")
    def _onchange_type_person_taxpayer_withholding(self):
        """Ticket 86944: a non resident partner has neither taxpayer type nor
        withholding type."""
        for partner in self:
            if partner._is_company_partner():
                continue
            if partner.is_non_resident_person:
                partner.taxpayer_type = "ordinary"
                partner.withholding_type_id = False
            elif partner.taxpayer_type == "special" and not partner.withholding_type_id:
                partner.withholding_type_id = self.env.ref(
                    "l10n_ve_payment_extension.account_withholding_type_75",
                    raise_if_not_found=False,
                )

    @api.onchange("taxpayer_type")
    def _onchange_taxpayer_type_withholding_type(self):
        """A special taxpayer gets the 75% withholding type by default and any
        other taxpayer type has none (ticket 16339). The partner of a company is
        left as it is: its withholding type comes from the company
        configuration."""
        withholding_75 = self.env.ref(
            "l10n_ve_payment_extension.account_withholding_type_75",
            raise_if_not_found=False,
        )
        for partner in self:
            if partner._is_company_partner() or partner.is_non_resident_person:
                continue
            if partner.taxpayer_type == "special":
                partner.withholding_type_id = withholding_75
            else:
                partner.withholding_type_id = False

    @api.constrains("type_person_id", "taxpayer_type")
    def _check_non_resident_taxpayer_type(self):
        # Only the special taxpayer type is rejected: existing flows (IVA
        # retentions) still read the withholding type of non resident partners.
        for partner in self:
            if partner.is_non_resident_person and partner.taxpayer_type == "special":
                raise ValidationError(
                    _("A non resident partner cannot be a special taxpayer.")
                )
