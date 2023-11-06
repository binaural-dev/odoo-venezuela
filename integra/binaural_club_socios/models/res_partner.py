from odoo import models, api, exceptions, fields, _
import logging
_logger = logging.getLogger()

class ResPartner(models.Model):
    _inherit = "res.partner"

    def actions_active(self):
        actions = []
        partner_action = self.env['res.partner'].search([('action_number', '!=', False)])
        for x in partner_action:
            actions.append(x.action_number.number)
        return [('number', 'not in', actions)]#tesoreria es disponible para asignar


    action_number = fields.Many2one('action.partner', string='Action Number')
    action_number_related = fields.Many2one('action.partner', string='Action related')
    
    is_solvent_related = fields.Boolean(string='Is solvent?')

      
    state_action = fields.Selection([
        ('active', 'Active'),
        ('special', 'Special'),
        ('honorary', 'Honorary'),
        ('treasury', 'Treasury'),
    ], 'Action State', store=True,track_visibility='onchange')

    state_partner = fields.Selection([
        ('active', 'Active'),
        ('holder', 'Holder'),
        ('deceased', 'Deceased'),
        ('inactive', 'Inactive'),
    ], 'State', default='active', required=True,track_visibility='onchange')


    other_doc_id = fields.Char(string='Other Identification Document',track_visibility='onchange')
    
    start_date = fields.Date('Start Date',track_visibility='onchange')
    birthday = fields.Date('Birthday',track_visibility='onchange')
    age = fields.Integer('Age')
    office_phone = fields.Char(string='Office Phone',track_visibility='onchange')
    mobile_phone_two  = fields.Char(string='Additional Cell Phone',track_visibility='onchange')
    aditional_email  = fields.Char(string='Additional Email',track_visibility='onchange')

    member_type  = fields.Selection([
        ('action', 'Action'),
        ('extension', 'Extension')
    ], string='Member Type', track_visibility='onchange')
    
    business_name_usufruct = fields.Char(string='Business name usufruct',track_visibility='onchange')
    prefix_vat_usufruct = fields.Selection([
        ('v', 'V'),
        ('e', 'E'),
        ('j', 'J'),
        ('g', 'G'),
    ], 'Prefix vat usufruct', default='v',track_visibility='onchange')

    vat_usufruct = fields.Char(string='Vat Usufruct',track_visibility='onchange')
    address_usufruct = fields.Text(string='Address usufruct',track_visibility='onchange')

    is_solvent = fields.Boolean(string='Is solvent', default=True, track_visibility='onchange')

    member_company = fields.Char(string='Member Company')
    member_profession = fields.Many2one('partner.professions', string='Profession',track_visibility='onchange',domain=[('active','=',True)])
    member_gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], default="male",string="Sex",track_visibility='onchange')
    member_marital = fields.Selection([
        ('single', 'Single'),
        ('married', 'Married'),
        ('cohabitant', 'Cohabitant'),
        ('widower', 'Widower'),
        ('divorced', 'Divorced')
    ], string='Member Martial', default='single',track_visibility='onchange')
    member_contact_name =  fields.Char(string='Contact Member Name',track_visibility='onchange')
    member_contact_phone = fields.Char(String='Phone Contact Member Name',track_visibility='onchange')
    member_contact_email  = fields.Char(string='Email contact name',track_visibility='onchange')
 
    can_access_club = fields.Boolean(string='Can access club',default=True,track_visibility='onchange')
    #fecha de fin del socio
    end_date_partner = fields.Date('End date partner',track_visibility='onchange')
    alerted_end_date_partner = fields.Boolean('Alerted end date partner')

    #carga familiar
    type_relation = fields.Selection([
        ('partner', 'Partner'),
        ('associated', 'Associated'),
        ('wife', 'Wife'),
        ('children', 'Children'),
        ('parents','Parents'),
        ('special_children','Special Children'),
    ], string='Type relation', default=False, track_visibility='onchange')

    end_date_family = fields.Date('End date family',track_visibility='onchange')
    family_reference = fields.Char(string='Family reference',track_visibility='onchange')
    
    #asociado familiar
    associate_parent = fields.Many2one('res.partner', string='Associate parent',track_visibility='onchange')
    associate_action = fields.Many2one('action.partner', string='Associate action',related="associate_parent.action_number",track_visibility='onchange')
    associate_childs = fields.One2many('res.partner', 'parent_id', string='Associate Childs', domain=[('active', '=', True)],track_visibility='onchange')
    #campos referentes a la suspensión
    reason = fields.Text(string='Reason')
    end_date_suspend = fields.Date(string='End date suspend')
    start_date_suspend = fields.Date(string='Start date suspend')
    user_suspend = fields.Many2one('res.users',string='User suspend')
 
    
    prev_state_partner = fields.Selection([
        ('active', 'Active'),
        ('holder', 'Holder'),
        ('deceased', 'Deceased'),
        ('inactive', 'Inactive'),
    ], 'Previous State',default='active')

    #campos referentes a remover suspension
    user_remove_suspend = fields.Many2one('res.users',string='User remove suspend')
    date_remove_suspend  = fields.Date(string='Date remove suspend')
