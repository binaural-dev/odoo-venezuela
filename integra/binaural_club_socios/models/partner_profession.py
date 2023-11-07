from odoo import models, api, exceptions, fields, _
import logging

_logger = logging.getLogger(__name__)

class PartnerProfessions(models.Model):
    _name = 'partner.professions'
    _description = 'Professions'
    _rec_name = 'name'

    _sql_constraints = [
	    ('name_uniq', 'unique(name)', 'The name of the profession is already registered!'),
    ]
    name = fields.Char(string='Name')
    active = fields.Boolean(string='Active',default=True)



    @api.onchange('name')
    def upper_name(self):
        if self.name:
            self.name = self.name.upper()
