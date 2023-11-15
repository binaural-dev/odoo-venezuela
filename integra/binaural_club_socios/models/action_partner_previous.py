from odoo import models, api, exceptions, fields

class ActionPartnerPrevious(models.Model):
    _name = 'action.partner.previous'
    _description = 'Last action partners'

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )

    name = fields.Char('Name')
    identification = fields.Char('Identification')
    date_start = fields.Datetime('Start date')
    date_end = fields.Datetime('End date')
    action_id = fields.Many2one('action.partner', string='Action')
    type_operation = fields.Selection([
        ('link', 'Link'),
        ('unlink', 'Ulink'),
    ], string='Type operation')
    name_exec = fields.Char(string='User')
    date_exec = fields.Date(string='Operation Date')
    
