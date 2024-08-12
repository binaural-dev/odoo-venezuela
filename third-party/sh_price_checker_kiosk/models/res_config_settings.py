# Copyright (C) Softhealer Technologies.

from odoo import models,fields,api

class ResCompany(models.Model):
    _inherit='res.company'

    sh_product_stock = fields.Boolean("Show Available Stock")
    sh_product_attribute = fields.Boolean("Show Product Specification")
    sh_product_image = fields.Boolean("Show Product Image")
    sh_product_category = fields.Boolean("Show Product Category")
    sh_product_code = fields.Boolean("Show Product Code")
    sh_product_barcode = fields.Boolean("Show Product Barcode")
    sh_product_weight = fields.Boolean("Show Product Weight")
    sh_product_pricelist = fields.Boolean(
        "Show Product Pricelist")
    sh_product_sale_price = fields.Boolean("Show Product Sales Price")
    sh_product_sale_description = fields.Boolean(
        "Show Product Sales Description")
    sh_touch_kyboard = fields.Boolean("Show Keyboard")
    sh_welcome_message = fields.Boolean("Show Welcome Message")
    sh_message = fields.Char("Welcome Message")
    sh_company_logo = fields.Boolean(" Company Logo")
    sh_display = fields.Boolean("Display Setting")
    sh_display_view = fields.Selection(
        [('landscape', 'Landscape'), ('portrait', 'Portrait')], string='Product Specification Orientation')
    sh_display_landscape = fields.Selection(
        [('left', 'Left'), ('right', 'Right')], string='Product Specification  ')
    sh_display_portrait = fields.Selection(
        [('top', 'Top'), ('bottom', 'Bottom')], string='Product Specification ')
    sh_delay_screen = fields.Integer('Redirect To Kiosk (Seconds)', default=10)
    sh_search_char_field_product = fields.Many2many(
        'ir.model.fields', string="Search Char Fields in Product")
    sh_warehouse_ids = fields.Many2many('stock.warehouse', string="Warehouse")


class ResConfigSetting(models.TransientModel):
    _inherit='res.config.settings'

    @api.model
    def get_company_id_values(self):
        company_id = self.env.company
        return company_id

    company_id = fields.Many2one(
        'res.company', 'Company', default=get_company_id_values)
    sh_product_stock = fields.Boolean(
        "Show Available Stock ", related='company_id.sh_product_stock', readonly=False)
    sh_product_attribute = fields.Boolean(
        "Show Product Specification ", related='company_id.sh_product_attribute', readonly=False)
    sh_product_image = fields.Boolean(
        "Show Product Image ", related='company_id.sh_product_image', readonly=False)
    sh_product_category = fields.Boolean(
        "Show Product Category ", related='company_id.sh_product_category', readonly=False)
    sh_product_code = fields.Boolean(
        "Show Product Code ", related='company_id.sh_product_code', readonly=False)
    sh_product_barcode = fields.Boolean(
        "Show Product Barcode ", related='company_id.sh_product_barcode', readonly=False)
    sh_product_weight = fields.Boolean(
        "Show Product Weight", related="company_id.sh_product_weight", readonly=False)
    sh_product_pricelist = fields.Boolean(
        "Show Product Pricelist", related="company_id.sh_product_pricelist", readonly=False)
    sh_product_sale_price = fields.Boolean(
        "Show Product Sales Price ", related='company_id.sh_product_sale_price', readonly=False)
    sh_product_sale_description = fields.Boolean(
        "Show Product Sales Description ", related='company_id.sh_product_sale_description', readonly=False)
    sh_touch_kyboard = fields.Boolean(
        "Show Keyboard", related='company_id.sh_touch_kyboard', readonly=False)
    sh_welcome_message = fields.Boolean(
        "Show Welcome Message ", related='company_id.sh_welcome_message', readonly=False)
    sh_message = fields.Char(
        "Welcome Message ", related='company_id.sh_message', readonly=False)
    sh_company_logo = fields.Boolean(
        "Company Logo ", related='company_id.sh_company_logo', readonly=False)
    sh_display = fields.Boolean(
        "Display Setting ", related='company_id.sh_display', readonly=False)
    sh_display_view = fields.Selection(
        string='Product Specification Orientation ', related='company_id.sh_display_view', readonly=False)
    sh_display_landscape = fields.Selection(
        string='Product Specification ', related='company_id.sh_display_landscape', readonly=False)
    sh_display_portrait = fields.Selection(
        string=' Product Specification', related='company_id.sh_display_portrait', readonly=False)
    sh_delay_screen = fields.Integer(
        'Redirect To Kiosk (Seconds) ', related='company_id.sh_delay_screen', readonly=False)
    sh_search_char_field_product = fields.Many2many('ir.model.fields',
                                                    string="Search Product By", related='company_id.sh_search_char_field_product', readonly=False)
    sh_warehouse_ids = fields.Many2many(
        'stock.warehouse', string="Warehouse", related='company_id.sh_warehouse_ids', readonly=False)

    @ api.onchange('sh_display')
    def onchange_sh_display(self):
        if not self.sh_display:
            self.sh_display_view = False
            self.sh_display_landscape = False
            self.sh_display_portrait = False

    @api.onchange('sh_search_char_field_product')
    def onchange_sh_search_char_field_product(self):
        sh_model = self.env['ir.model'].sudo().search(
            [('model', '=', 'product.product')])
        domain = {}
        domain = {
            'sh_search_char_field_product': [('model_id', '=', sh_model.id), ('ttype', '=', 'char')]
        }
        return{'domain': domain}
    

