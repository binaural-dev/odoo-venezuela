from odoo import fields, models


class ResPartnerZone(models.Model):
    _name = "res.partner.zone"
    _description = "Zone"

    name = fields.Char(string="Name", required=True)
