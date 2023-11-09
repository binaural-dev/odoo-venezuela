
from odoo import models, api, exceptions, fields


class ActionPartner(models.Model):
    _name = 'action.partner'
    _description = 'Partner Action'
    _rec_name = 'number'

    _sql_constraints = [
	    ('number_uniq', 'unique(number, company_id)', 'El número de acción ya se encuentra registrado!'),
    ]

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    type_action = fields.Selection([
        ('action', 'Action'),
        ('extention', 'Extention'),
    ], 'Action Type', default='action', required=True,track_visibility='onchange')
    number = fields.Char('Number', required=True,track_visibility='onchange')
    state = fields.Selection([
        ('active', 'Active'),
        ('special', 'Special'),
        ('honorary', 'Honorary'),
        ('treasury', 'Treasury'),
    ], 'State', default='active', required=True,track_visibility='onchange')
    partners_previous_ids = fields.One2many('action.partner.previous', 'action_id', string='Socios Anteriores',track_visibility='onchange')