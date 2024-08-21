from odoo import models, api, exceptions, fields, _
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger()


class ResPartner(models.Model):
    _inherit = "res.partner"

    action_number = fields.Many2one(
        "action.partner", 
        string="Action Number", 
        domain=[("owner_id", "=", False)],
    )

    parent_action_number = fields.Many2one(
        "action.partner",
        string="Action Number Partner Related",
        compute="_compute_parent_action_number",
        store=True
    )

    hide_action_number = fields.Boolean(
        compute="_compute_hide_action_number"
    )

    readonly_action_number =  fields.Boolean()

    is_solvent_related = fields.Boolean(string="Is solvent?")

    state_action = fields.Selection(
        [
            ("active", "Active"),
            ("special", "Special"),
            ("honorary", "Honorary"),
            ("treasury", "Treasury"),
        ],
        "Action State",
        related="action_number.state",
        store=True,
        track_visibility="onchange",
    )

    state_partner = fields.Selection(
        [
            ("active", "Active"),
            ("holder", "Holder"),
            ("deceased", "Deceased"),
            ("inactive", "Inactive"),
        ],
        "State",
        default="active",
        required=True,
        track_visibility="onchange",
    )

    other_doc_id = fields.Char(string="Other Identification Document", track_visibility="onchange")

    start_date = fields.Date("Start Date", track_visibility="onchange")
    birthday = fields.Date("Birthday", track_visibility="onchange")
    age = fields.Integer("Age")
    office_phone = fields.Char(string="Office Phone", track_visibility="onchange")
    mobile_phone_two = fields.Char(string="Additional Cell Phone", track_visibility="onchange")
    aditional_email = fields.Char(string="Additional Email", track_visibility="onchange")

    member_type = fields.Selection(
        [("action", "Action"), ("extension", "Extension")],
        string="Member Type",
        related="action_number.type_action",
        track_visibility="onchange"
    )

    business_name = fields.Char()

    business_name_usufruct = fields.Char(
        string="Business name usufruct", track_visibility="onchange"
    )
    prefix_vat_usufruct = fields.Selection(
        [
            ("v", "V"),
            ("e", "E"),
            ("j", "J"),
            ("g", "G"),
        ],
        "Prefix vat usufruct",
        default="v",
        track_visibility="onchange",
    )

    vat_usufruct = fields.Char(string="Vat Usufruct", track_visibility="onchange")
    address_usufruct = fields.Text(string="Address usufruct", track_visibility="onchange")

    is_solvent = fields.Boolean(string="Is solvent", default=False, track_visibility="onchange")

    member_company = fields.Char(string="Member Company")
    member_profession = fields.Many2one(
        "partner.professions",
        string="Profession",
        track_visibility="onchange",
        domain=[("active", "=", True)],
    )
    member_gender = fields.Selection(
        [("male", "Male"), ("female", "Female"), ("other", "Other")],
        default="male",
        string="Sex",
        track_visibility="onchange",
    )
    member_marital = fields.Selection(
        [
            ("single", "Single"),
            ("married", "Married"),
            ("cohabitant", "Cohabitant"),
            ("widower", "Widower"),
            ("divorced", "Divorced"),
        ],
        string="Member Martial",
        default="single",
        track_visibility="onchange",
    )
    member_contact_name = fields.Char(string="Contact Member Name", track_visibility="onchange")
    member_contact_phone = fields.Char(
        String="Phone Contact Member Name", track_visibility="onchange"
    )
    member_contact_email = fields.Char(string="Email contact name", track_visibility="onchange")

    can_access_club = fields.Boolean(
        string="Can access club", default=True, track_visibility="onchange"
    )
    # fecha de fin del socio
    end_date_partner = fields.Date("End date partner", track_visibility="onchange")
    alerted_end_date_partner = fields.Boolean("Alerted end date partner")

    # carga familiar
    type_relation = fields.Selection(
        [
            ("partner", "Partner"),
            ("usufruct_partner", "Usufruct Partner"),
            ("associated", "Associated"),
            ("wife", "Wife"),
            ("children", "Children"),
            ("parents", "Parents"),
            ("special_children", "Special Children"),
        ],
        string="Type relation",
        default=False,
        track_visibility="onchange",
    )

    end_date_family = fields.Date("End date family", track_visibility="onchange")
    family_reference = fields.Char(string="Family reference", track_visibility="onchange")

    # asociado familiar
    associate_parent = fields.Many2one(
        "res.partner", string="Associate parent", track_visibility="onchange"
    )
    associate_action = fields.Many2one(
        "action.partner",
        string="Associate action",
        related="associate_parent.action_number",
        track_visibility="onchange",
    )
    associate_childs = fields.One2many(
        "res.partner",
        "associate_parent",
        string="Associate Childs",
        domain=[("active", "=", True)],
        track_visibility="onchange",
    )
    # campos referentes a la suspensión
    reason = fields.Text(string="Reason")
    end_date_suspend = fields.Date(string="End date suspend")
    start_date_suspend = fields.Date(string="Start date suspend")
    user_suspend = fields.Many2one("res.users", string="User suspend")

    prev_state_partner = fields.Selection(
        [
            ("active", "Active"),
            ("holder", "Holder"),
            ("deceased", "Deceased"),
            ("inactive", "Inactive"),
        ],
        "Previous State",
        default="active",
    )

    # campos referentes a remover suspension
    user_remove_suspend = fields.Many2one("res.users", string="User remove suspend")
    date_remove_suspend = fields.Date(string="Date remove suspend")
    has_ownership_conflict = fields.Boolean()

    @api.constrains('action_number', 'type_relation')
    def _check_action_number(self):
        for record in self:

            action_number = record.action_number
            partner_active = record.active
            
            has_action_number = bool(action_number)

            record.readonly_action_number = bool(has_action_number)
            
            if not has_action_number:
                continue

            # Assign owner of action_number
            if not action_number.owner_id and partner_active:
                action_number.owner_id = record.id
                record.readonly_action_number = True
                continue

            if action_number.owner_id.id == record.id:
                continue

            if not partner_active:
                raise UserError(
                _(
                    "Action %s can't be assigned to inactive partner.",
                    action_number.number
                )
            )

            raise UserError(
                _(
                    "Action %s is being used by %s.",
                    action_number.number,
                    action_number.owner_id.name
                )
            )

    @api.depends('supplier_rank', 'customer_rank')
    def _compute_hide_action_number(self):
        for record in self:
            record.hide_action_number = record.supplier_rank > 0 or record.customer_rank == 0

    @api.depends('parent_id.action_number', 'type_relation')
    def _compute_parent_action_number(self):
        for record in self:
            if not record.type_relation or record.type_relation == "partner":
                record.parent_action_number = None
                continue

            record.parent_action_number = record.parent_id.action_number

    @api.onchange("birthday")
    def _onchange_birthday(self):
        self._calculate_partner_birthday()

    def _calculate_partner_birthday(self):
        if self.birthday:
            edad = relativedelta(datetime.now(), self.birthday)
            self.age = edad.years
            if self.type == "contact" and self.type_relation == "children":
                # es una carga familiar y es hijo calcular vencimiento
                config = (
                    self.env["partner.config"]
                    .sudo()
                    .search(
                        [("active", "=", True), ("company_id", "=", self.env.company.id)], limit=1
                    )
                )
                if not config:
                    raise exceptions.UserError(
                        _(
                            "No partner configuration registered please contact your system administrator."
                        )
                    )
                self.end_date_family = self.birthday + relativedelta(
                    years=config.age_limit_for_associated_children
                )

    @api.onchange("start_date")
    def _onchange_start_date(self):
        if self.start_date:
            config = (
                self.env["partner.config"]
                .sudo()
                .search([("active", "=", True), ("company_id", "=", self.env.company.id)], limit=1)
            )
            if not config:
                raise exceptions.UserError(
                    "No partner configuration registered please contact your system administrator."
                )
            self.end_date_partner = self.start_date + relativedelta(
                years=config.years_of_membership
            )

    def action_transfer(self):
        for partner in self:
            if partner.member_type != "action":
                raise exceptions.UserError(_("You cannot transfer a holding partner"))
            if not partner.is_solvent or not partner.active:
                raise exceptions.UserError(_("You cannot transfer a delinquent or inactive share."))

            partner.action_number.action_transfer()
            partner.active = False

            partner.message_post(
                subject=_("Archived partner:(%s)") % partner.name,
                body=_("Archived partner %s on: %s, by action transfer")
                % (
                    partner.name,
                    fields.Date.today().strftime("%d/%m/%y"),
                ),
            )

            for parent_id in partner.child_ids:
                parent_id.active = False


    def action_approve_vote(self):
        for partner in self:
            config = (
                self.env["partner.config"]
                .sudo()
                .search([("active", "=", True), ("company_id", "=", self.env.company.id)], limit=1)
            )
            if not config:
                raise exceptions.UserError(
                    _(
                        "No partner configuration registered please contact your system administrator."
                    )
                )
            end_date_partner = fields.Date.today() + relativedelta(years=config.years_of_membership)
            partner.write(
                {
                    "state_partner": "active",
                    "start_date": fields.Date.today(),
                    "end_date_partner": end_date_partner,
                }
            )
            partner.message_post(
                subject=_("Voting process of:(%s)") % partner.name,
                body=_("Voting process of %s approved the:: %s, by %s")
                % (
                    partner.name,
                    fields.Date.today().strftime("%d/%m/%y"),
                    self.env.user.name,
                ),
            )

    def action_establish_extension(self):
        try:
            form_view_id = self.env.ref(
                "binaural_club_socios.binaural_club_socios_form_establish_extension"
            ).id
        except Exception as e:
            form_view_id = False
        return {
            "type": "ir.actions.act_window",
            "name": "Establish Extension: " + self.name,
            "binding_view_types": "form",
            "view_mode": "form",
            "res_model": "establish.extension",
            "views": [(form_view_id, "form")],
            "view_id": form_view_id,
            "target": "new",
            "context": {
                "default_partner_to_establish": self.id,
            },
        }

    def action_suspend_partner(self):
        try:
            form_view_id = self.env.ref(
                "binaural_club_socios.binaural_club_socios_form_suspend_partner"
            ).id
        except Exception as e:
            form_view_id = False
        return {
            "type": "ir.actions.act_window",
            "name": "Suspend: " + self.name,
            "binding_view_types": "form",
            "view_mode": "form",
            "res_model": "suspend.partner",
            "views": [(form_view_id, "form")],
            "view_id": form_view_id,
            "target": "new",
            "context": {
                "default_partner_to_suspend": self.id,
            },
        }

    def action_remove_suspend_partner(self):
        try:
            form_view_id = self.env.ref(
                "binaural_club_socios.binaural_club_socios_form_remove_suspend_partner"
            ).id
        except Exception as e:
            form_view_id = False
        return {
            "type": "ir.actions.act_window",
            "name": "Remover suspension de: " + self.name,
            "binding_view_types": "form",
            "view_mode": "form",
            "res_model": "remove.suspend.partner",
            "views": [(form_view_id, "form")],
            "view_id": form_view_id,
            "target": "new",
            "context": {
                "default_partner_to_remove_suspend": self.id,
            },
        }

    @api.onchange("action_number")
    def update_action_partner_and_contact(self):
        for record in self:
            if record.action_number:
                if record.type not in ["contact"]:
                    record.write(
                        {"display_name": "%s - " % str(record.action_number.number) + record.name}
                    )
                else:
                    for x in record.child_ids:
                        search_ind_contact = x.display_name.find("-")
                        search_ind = x.display_name.find(",")
                        x.write(
                            {
                                "display_name": x.display_name[: search_ind + 1]
                                + "%s - " % str(x.parent_id.action_number.number)
                                + x.display_name[search_ind_contact + 1 :]
                            }
                        )

    def _compute_display_name(self):
        for partner in self:
            name = partner.name or ""

            if partner.company_name or partner.parent_id:
                if not name and partner.type in ["invoice", "delivery", "other"]:
                    name = dict(self.fields_get(["type"])["type"]["selection"])[partner.type]
                if not partner.is_company:
                    name = "%s, %s" % (
                        partner.commercial_company_name or partner.parent_id.name,
                        "%s - " % str(partner.parent_id.action_number.number) + name,
                    )
            if self._context.get("show_address_only"):
                name = partner._display_address(without_company=True)
            if self._context.get("show_address"):
                name = name + "\n" + partner._display_address(without_company=True)
            name = name.replace("\n\n", "\n")
            name = name.replace("\n\n", "\n")
            if self._context.get("show_email") and partner.email:
                name = "%s <%s>" % (name, partner.email)
            if self._context.get("html_format"):
                name = name.replace("\n", "<br/>")
            if partner.action_number:
                name = "%s - %s" % (partner.action_number.number, name)
            res.append((partner.id, name))
        return res

    @api.model
    def _commercial_fields(self):
        include_vat = self.env.context.get("include_vat", True)

        if include_vat:
            return ['vat', 'company_registry', 'industry_id']

        return ['company_registry', 'industry_id']

    def _fields_sync(self, values):
        """ Sync commercial fields and address fields from company and to children after create/update,
        just as if those were all modeled as fields.related to the parent """
        # 1. From UPSTREAM: sync from parent
        if values.get('parent_id') or values.get('type') == 'contact':
            # 1a. Commercial fields: sync if parent changed

            include_vat = values.get('type') != 'contact'

            if values.get('parent_id'):
                self.with_context(include_vat=include_vat).sudo()._commercial_sync_from_company()

            # 1b. Address fields: sync if parent or use_parent changed *and* both are now set
            if self.parent_id and self.type == 'contact':
                onchange_vals = self.onchange_parent_id().get('value', {})
                self.update_address(onchange_vals)

        # 2. To DOWNSTREAM: sync children
        self._children_sync(values)

    def action_resolve_ownership_conflict(self):
        for record in self:
            owner_ids = self.env["res.partner"].search([
                ("action_number", "=", record.action_number.id),
                ("id", "!=", record.id)
            ])

            if not owner_ids:
                continue

            owner_ids.write({
                "action_number": None,
                "has_ownership_conflict": False,
            })
            
            record.action_number.owner_id = record.id

            record.has_ownership_conflict = False

    @api.model
    def _show_ownership_conflict_resolve_button(self):
        action_number_ids = self.env["action.partner"].search([])

        exist_ownership_conflict = False

        for record in action_number_ids:

            owner_ids = self.env["res.partner"].search([
                ("action_number", "=", record.id)
            ])

            if len(owner_ids) <= 1:
                continue

            owner_ids.write({
                "has_ownership_conflict": True,
            })

            exist_ownership_conflict = True

        return exist_ownership_conflict

    def _reset_ownership_action_number(self):
        for record in self:

            has_action_number = bool(record.action_number)
            record.readonly_action_number = bool(has_action_number)

            if has_action_number:
                record.action_number.owner_id = record.id

    def cron_resolve_ownership_action_number(self):
        records = self.env["res.partner"].search([
            ("action_number", "!=", False)
        ])

        exist_ownership_conflict = self._show_ownership_conflict_resolve_button()

        if exist_ownership_conflict:
            _logger.warning('--------exist_ownership_conflict-------------')
            _logger.warning(exist_ownership_conflict)
            _logger.warning('---------------------')
            return False

        records._reset_ownership_action_number()
