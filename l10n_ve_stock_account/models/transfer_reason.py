from odoo import models, fields, api

class TransferReason(models.Model):
    _name = "transfer.reason"
    _description = "Reasons for Stock Transfer"

    name = fields.Char(string="Reason", required=True)
    code = fields.Char(string="Code", required=True)
    active = fields.Boolean(string="Active", default=True)
