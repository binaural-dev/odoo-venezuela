from odoo import api, models, _
from odoo.exceptions import UserError
from datetime import date
from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)

class ReportMemberList2(models.AbstractModel):
	_name = 'report.binaural_payment_reports.advance_payment_template_report'

	@api.model
	def _get_report_values(self, docids, data=None):
		if not data.get('form') or not self.env.context.get('active_model') or not self.env.context.get('active_id'):
			raise UserError(_("Form content is missing, this report cannot be printed."))
		ctx = data.get('context',False)
		name_user = ''
		if ctx:
			uid = ctx.get('uid')
			obj_uid = self.env['res.users'].sudo().search([('id','=',uid)])
			if obj_uid:
				name_user = obj_uid.name
		form = data.get('form',False)
		if not form:
			raise UserError(_("Error en formulario de reporte"))
		docs = self.env['advance.payment.report'].browse(self.env.context.get('active_id'))

		report_type = form.get('report_type',False)
		payment_type = form.get('payment_type',False)
		all_partner = form.get('all_partner',False)
		partner = form.get('partner_id',False)
		at_today = form.get('at_today',False)
		start_date = form.get('start_date',False)
		end_date = form.get('end_date',False)
		residual_type = form.get('residual_type',False)

		search_domain = []
		domain = []
		name_report = 'Listado de anticipos'
		if payment_type == 'advance':
			if report_type == 'supplier':
				search_domain += [('payment_type','=','outbound')]
				domain += [('supplier_rank','>',0)]
				name_report = 'Listado de anticipos de proveedores'
			else:
				search_domain += [('payment_type','=','inbound')]
				domain += [('customer_rank','>',0)]
				name_report = 'Listado de anticipos de clientes'
		else:
			if report_type == 'supplier':
				search_domain += [('payment_type','=','outbound')]
				domain += [('supplier_rank','>',0)]
				name_report = 'Listado de pagos de proveedores'
			else:
				search_domain += [('payment_type','=','inbound')]
				domain += [('customer_rank','>',0)]
				name_report = 'Listado de pagos de clientes'

		client_ids = []
				
		if not all_partner and partner:
			client_ids = self.env['res.partner'].sudo().browse(partner)
		else:
			if report_type and report_type == 'supplier':
				search_domain += [('payment_type','=','outbound')]
			else:
				search_domain += [('payment_type','=','inbound')]

			if payment_type == 'advance':
				search_domain += [('is_advance_payment','=',True)]
			elif payment_type == 'payment':
				search_domain += [('is_advance_payment','=',False)]
			# elif type_payment and type_payment == 'is_expense':
			# 	search_domain += [('is_expense','=',True)]

			if at_today:
				search_domain += [('date','<=',fields.Date.today())]
			else:
				search_domain += [('date','<=',end_date),('date','>=',start_date)]

			payments = self.env['account.payment'].sudo().search(search_domain)
			if residual_type != 'all':
				new_payments = []
				for p in payments:
					acum = docs.get_residual_by_payment(p)
					if(acum == 0 and residual_type == 'not_residual') or (acum != 0 and residual_type == 'residual'):
						new_payments.append(p)
				payments = new_payments
			#buscar todos los pagos con el criterio del wizard para saber los clientes que debo buscar
			for p in payments:
				if p.partner_id not in client_ids:
					client_ids.append(p.partner_id)
			client_ids = self.env['res.partner'].sudo().search(domain) #buscos todos los clientes



		return {
			'data': data['form'],
			'docs': docs,
			'client_ids':client_ids,
			'date':date.today(),
			'name_user':name_user,
			'name_report':name_report,
		}


