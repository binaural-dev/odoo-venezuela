#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
# 
#################################################################################
from odoo import api, fields, models
from odoo.exceptions import ValidationError
import re

class PosKeyboardShortcuts(models.Model):
    _name = "pos.keyboard.shortcuts"

    name = fields.Char(required=True)

    # Product Screen Shotcuts
    next_screen = fields.Char(string="Next Screen",size=1,default="N")
    customer_screen = fields.Char(string="Customer Screen",size=1,default="C")
    search_product = fields.Char(string="Search Product",size=1,default="S")
    select_previous_orderline = fields.Char(string="Select Previous Orderline",default="ArrowDown")
    select_next_orderline = fields.Char(string="Select Next Orderline",default="ArrowUp")
    select_qty = fields.Char(string="Select Quantity in Numpad",size=1,default="Q")
    select_discount = fields.Char(string="Select Discount in Numpad",size=1,default="D")
    select_info = fields.Char(string="Select Info Button",size=1,default="F")
    select_refund = fields.Char(string="Select Refund Button",size=1,default="E")
    
    select_price = fields.Char(string="Select Price in Numpad",size=1,default="P")
    create_customer = fields.Char(string="Add a Customer",size=1,default="A")
    delete_orderline_data = fields.Char(string="Delete Quantity/Discount/Price of Orderline",default="Backspace")
    navigate_product_left = fields.Char(string="Navigate Product Left",default="ArrowLeft")
    navigate_product_right = fields.Char(string="Navigate Product Right",default="ArrowRight")
    
    # Payment Screen Shortcuts
    order_invoice = fields.Char(string="Order Invoice",size=1,default="I")    
    payment_methods = fields.One2many(comodel_name='pos.payment.method.key', inverse_name='shortcut_payment_method_ids')

    # Customer Screen Shortcuts
    select_customer = fields.Char(string="Select/Deselect Customer",default="Enter")

    # Receipt Screen Shortcutsre.
    print_receipt = fields.Char(string="Print Receipt",size=1,default="R")
    next_screen_show = fields.Char(string="Show Next Screen",default="Enter")

    #Common Shortcuts
    back_screen = fields.Char(string="Back Screen",size=1,default="B")
    click_ok = fields.Char(string="Ok Button of Popup",default="Enter")
    click_cancel = fields.Char(string="Cancel Button in Popup",default="Escape")
    see_all_order = fields.Char(string="Show Orders",default="O")

    select_user = fields.Char(string="Select POS User",size=1,default="U")
    refresh = fields.Char(string="Refresh Connection", size=1, default="Z")
    close_pos = fields.Char(string="Close POS Session", size=1, default="M")

    @api.constrains('next_screen','customer_screen','search_product','select_qty','select_discount','select_info','select_refund','select_price','create_customer','order_invoice','print_receipt','back_screen','payment_methods')
    def check_shortcuts(self):
        if(self.payment_methods):
            count = {}
            for data in self.payment_methods:
                if data.payment_method_id.name in count:
                    raise ValidationError('Cannot Use '+ data.payment_method_id.name + ' Payment Method Again')
                count[data.payment_method_id.name] = 1

        check = []
        if(self.next_screen):
            check.append(self.next_screen)
        if(self.customer_screen):
            check.append(self.customer_screen)
        if(self.search_product):
            check.append(self.search_product)
        if(self.select_qty):
            check.append(self.select_qty)
        if(self.select_discount):
            check.append(self.select_discount)
        if(self.select_info):
            check.append(self.select_info)
        if(self.select_refund):
            check.append(self.select_refund)
       
        if(self.select_price):
            check.append(self.select_price)
        if(self.create_customer):
            check.append(self.create_customer)
        if(self.order_invoice):
            check.append(self.order_invoice)
        if(self.print_receipt):
            check.append(self.print_receipt)
        if(self.back_screen):
            check.append(self.back_screen)
       
        payment_methods_vals = self.payment_methods.read([]) 
        for vals in payment_methods_vals:
            if(vals['key_journals']):
                check.append(vals['key_journals'])
        
        data = {}
        for obj in check:
            result = re.match('[a-zA-Z]+',obj)
            if(result == None):
                raise ValidationError('Enter a valid Key for shortcut.')
            if obj.upper() in data:
                raise ValidationError("Please try again with new keyword, "+obj+" is already in use.")  
            else:
                data[obj.upper()] = 1

class PosConfig(models.Model):
    _inherit = 'pos.config'

    select_shortcut = fields.Many2one('pos.keyboard.shortcuts',string='Choose Shortcut')
    enable_shortcuts = fields.Boolean(string="Shortcuts",help="Enable shorcuts setting from the point of sale")

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_select_shortcut = fields.Many2one(related='pos_config_id.select_shortcut', readonly=False)
    pos_enable_shortcuts = fields.Boolean(related='pos_config_id.enable_shortcuts', readonly=False)

class PosPaymentMethodKey(models.Model):
    _name = "pos.payment.method.key"

    shortcut_payment_method_ids = fields.Many2one('pos.keyboard.shortcuts',string='Keyboards Shortcuts')
    payment_method_id = fields.Many2one('pos.payment.method',string="Payment Method")
    key_journals = fields.Char(string="key code",size=1)

class PosSession(models.Model):
    _inherit = 'pos.session'

    def _pos_ui_models_to_load(self):
        result = super()._pos_ui_models_to_load()
        if 'pos.keyboard.shortcuts' not in result:
            result.append('pos.keyboard.shortcuts')
        if 'pos.payment.method.key' not in result:
            result.append('pos.payment.method.key')
        return result

    def _loader_params_pos_keyboard_shortcuts(self):
        if self.config_id and self.config_id.enable_shortcuts and self.config_id.select_shortcut:
            return {'search_params': {'domain': [('id', '=', self.config_id.select_shortcut.id)], 'fields': []}}
        else:
            return {'search_params': {'domain': [], 'fields': []}}

    def _get_pos_ui_pos_keyboard_shortcuts(self, params):
        if self.config_id and self.config_id.enable_shortcuts and self.config_id.select_shortcut:
            return self.env['pos.keyboard.shortcuts'].search_read(**params['search_params'])
        else:
            return []

    def _loader_params_pos_payment_method_key(self):
        return {'search_params': {'domain': [], 'fields': []}}

    def _get_pos_ui_pos_payment_method_key(self, params):
        if self.config_id and self.config_id.enable_shortcuts and self.config_id.select_shortcut:
            return self.env['pos.payment.method.key'].search_read(**params['search_params'])
        else:
            return []