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

    @api.model
    def _l10n_ve_branch_synced_fields(self):
        """Fiscal fields that branches inherit from their root company partner."""
        return ["type_person_id", "withholding_type_id", "taxpayer_type"]

    def _l10n_ve_root_fiscal_values(self):
        """Synced fiscal fields that this root company partner has set, in write format.

        A field empty on the root is left out: it must not replace the value of a branch.
        """
        self.ensure_one()
        return {
            fname: self._fields[fname].convert_to_write(self[fname], self)
            for fname in self._l10n_ve_branch_synced_fields()
            if self[fname]
        }

    def _l10n_ve_propagate_fiscal_fields_to_branches(self, values, branches=None):
        """Write on the branches the fiscal values written on a root company partner.

        Only the synced fields present in ``values`` are written, so a field that was not
        touched on the root is not touched on the branches either.

        :param values: fields to write, in write format (many2one as id)
        :param branches: ``res.company`` records to write on. By default, every branch
            (any level, archived too) of the root companies whose partner is in ``self``.
        """
        synced = self._l10n_ve_branch_synced_fields()
        values = {fname: value for fname, value in values.items() if fname in synced}
        if not values:
            return
        if branches is None:
            Company = self.env["res.company"].sudo().with_context(active_test=False)
            roots = Company.search([("partner_id", "in", self.ids), ("parent_id", "=", False)])
            branches = Company.search(
                [("id", "child_of", roots.ids), ("id", "not in", roots.ids)]
            )
        branches.sudo().partner_id.write(values)

    def _fields_sync(self, values):
        super()._fields_sync(values)
        self._l10n_ve_propagate_fiscal_fields_to_branches(values)

    @api.constrains(lambda self: self._l10n_ve_branch_synced_fields())
    def _l10n_ve_check_branch_fiscal_fields(self):
        """Branch partners must keep the fiscal values of their root company partner.

        A field empty on the root is not compared: the root has no value to impose there.
        """
        branches = self.env["res.company"].sudo().with_context(active_test=False).search(
            [("partner_id", "in", self.ids), ("parent_id", "!=", False)]
        )
        for branch in branches:
            root_partner = branch.root_id.partner_id
            for fname in self._l10n_ve_branch_synced_fields():
                if root_partner[fname] and branch.partner_id[fname] != root_partner[fname]:
                    raise ValidationError(
                        _(
                            "The field %(field)s of a branch cannot differ from its root "
                            "company. Edit it in the contact of the root company %(root)s.",
                            field=self._fields[fname]._description_string(self.env),
                            root=branch.root_id.name,
                        )
                    )

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