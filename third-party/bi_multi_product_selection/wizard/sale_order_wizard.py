from odoo import _, api, fields, models, tools



class SelectProductWizard(models.TransientModel):

    _name =  'sale.order.wizard'
    _description = 'Sale Order Wizard'

    product_ids = fields.Many2many('product.product',string="Select Products" ,required=True)
    
    
    def confirm_sale_product(self):
        active_id = self.env.context.get('active_ids', [])
        get_active_id = self.env['sale.order'].browse(active_id) 
        get_active_ids = self.env['sale.order.line'].browse(active_id)   
        get_active_wizard_ids = self.env['sale.order.wizard'].browse(active_id)   
        productobj = self.env['sale.order.wizard'].search([('id', '=', self._context.get('active_id'))])  
        order_line_vals  = self.env['sale.order'].search([])
        line_vals = self.product_ids     
        line_env = self.env['sale.order.line']
        if get_active_id.state == 'draft':
            for wizard in self:
                for data in wizard.product_ids:
                    new_line = line_env.create({
                                'product_id': data.id,             
                                'order_id': get_active_id.id,
                                'state': 'draft',
                                
                                })      
        return True
        
      


    
