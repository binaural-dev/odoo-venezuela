from odoo import models, api, exceptions, fields, _
# from . import validations


class PartnerProfessions(models.Model):
    _name = 'partner.professions'
    _description = 'Professions'
    _rec_name = 'name'

    _sql_constraints = [
	    ('name_uniq', 'unique(name)', 'The name of the profession is already registered!'),
    ]
    name = fields.Char(string='Name')
    active = fields.Boolean(string='Active',default=True)

    # @api.onchange('name')
    # def upper_name(self):
    #     return validations.case_upper(self.name, "name")