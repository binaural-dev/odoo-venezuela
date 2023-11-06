
from odoo import api, fields, exceptions, http, models, _
from odoo.exceptions import UserError


class StatusActionBatch(models.TransientModel):
	_name = "status.action.batch"

	status = fields.Selection([
		('active', 'Active'),
		('special', 'Special'),
		('honorary', 'Honorary'),
		('treasury', 'Treasury'),
	], 'New State', required=True)

	actions_ids = fields.Many2many('action.partner', string='Actions',required=True)

	def change_status(self):

		if not self.status:
			raise UserError(_("New status is required"))
		if not self.actions_ids:
			raise UserError(_("Actions Required"))
		for p in self.actions_ids:
			p.update({'state':self.status})