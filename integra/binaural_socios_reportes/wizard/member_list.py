from odoo import api, fields, exceptions, http, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError

class MemberList(models.TransientModel):
    _name = "member.list.wizard"

    status = fields.Selection([
		('all','All'),
		('active', 'Active'),
		('holder', 'Holder'),
		('deceased', 'Deceased'),
		('inactive', 'Inactive'),
	], 'Estate', required=True,default='all')
    
    
    state_action = fields.Selection([
		('all', 'All'),
		('active', 'Active'),
		('special', 'Special'),
		('honorary', 'Honorary'),
		('treasury', 'Treasury'),
	], 'Action State',default='all',required=True)
    
    
    def print_pdf_member_list(self):
        if not self.status:
            raise UserError("Required State")
        if not self.state_action:
            raise UserError("Required state action")
            
        data = {'form':{'status': self.status,'state_action': self.state_action}}
        return self.env.ref('binaural_socios_reportes.action_report_member_list').with_context(landscape=True).report_action(self, data=data)
