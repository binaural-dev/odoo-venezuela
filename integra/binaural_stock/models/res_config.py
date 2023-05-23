from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
	_inherit = 'res.config.settings'

	use_main_warehouse = fields.Boolean(string='Usar almacén principal')
	main_warehouse_id = fields.Many2one("stock.warehouse", string="Almacén principal")

	def set_values(self):
		super(ResConfigSettings, self).set_values()
		
		self.env['ir.config_parameter'].sudo().set_param('use_main_warehouse', self.use_main_warehouse)
		self.env['ir.config_parameter'].sudo().set_param('main_warehouse_id', self.main_warehouse_id.id)

	@api.model
	def get_values(self):
		res = super(ResConfigSettings, self).get_values()

		res['use_main_warehouse'] = self.env['ir.config_parameter'].sudo().get_param('use_main_warehouse')
		res["main_warehouse_id"] = int(self.env['ir.config_parameter'].sudo().get_param('main_warehouse_id'))

		return res
