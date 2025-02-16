import re

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    taxpayer_type = fields.Selection(
        [
            ("formal", "Formal"),
            ("special", "Special"),
            ("ordinary", "Ordinary"),
        ],
        default="ordinary",
        store=True,
    )
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
    )

    country_id = fields.Many2one("res.country", default=lambda self: self.env.ref("base.ve", raise_if_not_found=False))
    municipality_id = fields.Many2one("res.country.municipality", "Municipality")
    parish_id = fields.Many2one("res.country.parish", "Parish")
    full_vat = fields.Char(string="RIF", compute="_compute_full_vat", store=True)

    @api.depends("prefix_vat", "vat")
    def _compute_full_vat(self):
        for partner in self:
            partner.full_vat = f"{partner.prefix_vat}-{partner.vat or ''}".ljust(11, "0")

    @api.constrains("vat")
    def _check_vat(self):
        pattern = "^[0-9]*$"
        for record in self:
            if record.vat:
                if not re.match(pattern, record.vat):
                    raise ValidationError(_("The vat field only accepts numbers"))

    @api.onchange("municipality_id")
    def _onchange_municipality_id(self):
        self.parish_id = False

    @api.onchange("state_id")
    def _onchange_state_id(self):
        self.municipality_id = False
        self.parish_id = False
