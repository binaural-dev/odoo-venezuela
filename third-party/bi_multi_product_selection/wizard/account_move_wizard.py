from odoo import _, api, fields, models, tools



class AccountMoveWizard(models.TransientModel):

    _name =  'account.move.wizard'
    _description = 'Account Move Wizard'

    product_ids = fields.Many2many('product.product',string="Select Products", required=True)

    def confirm_invoice_product(self):
        active_id = self.env.context.get('active_ids', [])
        get_active_id = self.env['account.move'].browse(active_id)
        get_active_ids = self.env['account.move.line'].browse(active_id) 
        get_active_wizard_ids = self.env['account.move.wizard'].browse(active_id) 
        productobj = self.env['account.move.wizard'].search([('id', '=', self._context.get('active_id'))])
        order_line_vals  = self.env['account.move'].search([])
        line_vals = self.product_ids

        line_env = self.env['account.move.line']
        if get_active_id.state == 'draft':
            for wizard in self:
                for data in wizard.product_ids:
                    new_line = line_env.create({
                                'product_id': data.id,             
                                'move_id': get_active_id.id,
                                
                                })     
        return True
      