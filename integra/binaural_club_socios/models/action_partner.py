from odoo import models, api, exceptions, fields, _
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)


class ActionPartner(models.Model):
    _name = "action.partner"
    _description = "Partner Action"
    _inherit = ["portal.mixin", "mail.thread"]

    _rec_name = "number"

    _sql_constraints = [
        (
            "number_uniq",
            "unique(number, company_id)",
            "El número de acción ya se encuentra registrado!",
        ),
    ]

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    type_action = fields.Selection(
        [
            ("action", "Action"),
            ("extention", "Extention"),
        ],
        "Action Type",
        default="action",
        required=True,
        track_visibility="onchange",
    )
    number = fields.Char("Number", required=True, track_visibility="onchange")
    state = fields.Selection(
        [
            ("active", "Active"),
            ("special", "Special"),
            ("honorary", "Honorary"),
            ("treasury", "Treasury"),
        ],
        "State",
        default="active",
        required=True,
        track_visibility="onchange",
    )
    partners_previous_ids = fields.One2many(
        "action.partner.previous",
        "action_id",
        string="Socios Anteriores",
        track_visibility="onchange",
    )

    owner_id = fields.Many2one(
        "res.partner",
        ondelete='restrict',
        track_visibility="onchange",
    )

    beneficiary_partner_ids = fields.One2many(
        'res.partner',
        'parent_action_number',
        string='Beneficiaries',
        store=True
    )
    
    @api.constrains('owner_id')
    def _check_owner_id(self):
        for record in self:

            # If everything is fine just one owner must to be
            owner_ids = self.env["res.partner"].search([
                ("action_number", "=", self.id)
            ])
            
            if len(owner_ids) <= 1:
                continue

            raise ValidationError(
                _(
                    "Action %s is being used by more than one owner. Resolve ownership conflict: %s.",
                    self.number,
                    ", ".join(owner_ids.mapped("vat"))
                )
            )

    def _prep_action_partner_previous(self):
        self.ensure_one()

        owner_id = self.owner_id

        value = {
            "name": owner_id.name,
            "identification": f"{owner_id.prefix_vat}{owner_id.vat}",
            "date_start": owner_id.start_date,
            "date_end": owner_id.end_date_partner,
            "action_id": owner_id.action_number.id,
            "type_operation": "unlink",
            "name_exec": self.env.user.name,
            "date_exec": fields.Date.today(),
        }
        
        return value

    def action_transfer(self):
        self.ensure_one()

        previous_owner_values = self._prep_action_partner_previous()

        self.owner_id.action_number = None
        self.owner_id = None

        self.env["action.partner.previous"].sudo().create(previous_owner_values)

    def write(self, vals):
        res = super().write(vals)
        if "type_action" in vals:
            self.message_post(
                body=_("Type Action changed to %s by %s el: %s")
                % (
                    self.type_action,
                    self.env.user.name,
                    fields.Date.today().strftime("%d/%m/%y"),
                )
            )
        if "state" in vals:
            self.message_post(
                body=_("Action changed to %s, by %s")
                % (
                    self.state,
                    self.env.user.name,
                )
            )
        if "owner_id" in vals:
            self.message_post(
                body=_("Owner changed to %s, by %s")
                % (
                    self.owner_id.name,
                    self.env.user.name,
                )
            )
        return res
