from odoo import models, fields,api,_

class ProductTemplateZmart(models.Model):
	_inherit = 'product.template'

	oem = fields.Many2one(
    	'product.template.oem',
    	store = True
    )
	oem_code = fields.Char(
    	store = True,
    	string = 'Código OEM'
    )
	zmart_code = fields.Char(
    	related = 'default_code', 
    	string = "Código Zmart",
    	store = True,
    	readonly = False
    	)
	serie = fields.Char(
    	store = True
    )
	color = fields.Char(
    	store = True
    )
	performance_pages = fields.Char(
    	store = True
    )
	compatibility = fields.Char(
    	store = True
    )
	warranty = fields.Char(
    	store = True
    )
	specification = fields.Char(
    	store = True
    )
	tariff_code = fields.Many2one(
    	'product.template.tariff',
    	store = True
    )
	percentage_tariff_code = fields.Float(
    	string = "Arancel  %",
    	store = True
    )
	gross_weight_inner_box = fields.Float(
    	store = True
    )
	gross_weight_master_carton = fields.Float(
    	store = True
	)
	unit_of_measurement_unit_sale = fields.Char(
    	store = True
    )
	unit_of_measurement_inner_box = fields.Char(
		store = True
	)
	unit_of_meassure_master_carton = fields.Char(
    	store = True
	)
	master_box_volume = fields.Float(
    	store = True
    )
	packaging_type = fields.Many2one(
    	'product.template.packaging',
    	store=True
    )
	sales_units_pieces = fields.Float(
    	store = True
    )
	quantity_of_inner_per_master = fields.Float(
    	store = True
    )
	quantity_units_per_master_box = fields.Float(
    	store = True
    )
	barcode_inner_box = fields.Char(
    	store = True
    )
	barcode_master_box = fields.Char(
    	store = True
    )
	long_unit = fields.Float(
    	store = True
    )
	wide_unit = fields.Float(
    	store = True
    )
	high_unit = fields.Float(
    	store = True
    )
	long_bulk = fields.Float(
    	store = True
    )
	wide_bulk = fields.Float(
    	store = True
    )
	high_bulk = fields.Float(
    	store = True
    )
	volume_ml = fields.Float(
    	store = True
    )
	sales_unit_gross_weight = fields.Float(
    	store = True
    )
	model_product = fields.Char(
		store = True
	)

	@api.depends('oem', 'oem.code')
	def _compute_code(self):
		for record in self:
			code = record.oem.code if record.oem else False
			record.oem_code = code