
from odoo import models, fields, api


class ResPartner(models.Model):

    _inherit = "res.partner"

    withholding_type_id = fields.Many2one(
        "account.withholding.type",
        string="Withholding Type",
        domain=[("state", "=", True)],
        track_visibility="onchange",
    )

    iva_account = fields.Many2one(
        "account.account", string="IVA Account", track_visibility="onchange"
    )

    islr_account = fields.Many2one(
        "account.account", string="ISLR Account", track_visibility="onchange"
    )

    taxpayer_type = fields.Selection(
        [
            ("formal", "Formal"),
            ("special", "Special"),
            ("ordinary", "Ordinary"),
        ],
        default="ordinary",
    )

    type_person_id = fields.Many2one("type.person", "Type Person", track_visibility="onchange")

    supplier_islr_account = fields.Many2one(
        "account.account",
        string="Supplier ISLR Account",
        track_visibility="onchange",
    )

    supplier_iva_account = fields.Many2one(
        "account.account",
        string="Supplier IVA Account",
        track_visibility="onchange",
    )

    exempt_iva = fields.Boolean("Exempt IVA", default=True, track_visibility="onchange")

    exempt_islr = fields.Boolean("Exempt ISLR", default=True, track_visibility="onchange")
