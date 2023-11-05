from odoo import _, api, fields, models, tools



class StockPickingWizard(models.TransientModel):

    _name =  'stock.picking.wizard'
    _description = 'Stock Move Wizard'

    product_ids = fields.Many2many('product.product',string="Select Products", required=True)

    def confirm_stock_picking_product(self):
      
        active_id = self.env.context.get('active_ids', [])
        get_active_id = self.env['stock.picking'].browse(active_id) 
        get_active_ids = self.env['stock.move'].browse(active_id)
        get_active_wizard_ids = self.env['stock.picking.wizard'].browse(active_id)  
        productobj = self.env['stock.picking.wizard'].search([('id', '=', self._context.get('active_id'))])
        order_line_vals  = self.env['stock.picking'].search([])
        line_vals = self.product_ids

        line_env = self.env['stock.move']
        if get_active_id.state == 'draft':
            for wizard in self:
                for data in wizard.product_ids:
                    new_line = line_env.create({
                                'name':data.name,
                                'product_id': data.id,             
                                'picking_id': get_active_id.id,
                                'location_id':get_active_id.location_id.id,
                                'location_dest_id': get_active_id.location_dest_id.id
                                
                                })     
        return True
      