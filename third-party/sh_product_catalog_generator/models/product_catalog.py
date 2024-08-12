# Copyright (C) Softhealer Technologies.

from odoo import models, fields


class ProductCatalog(models.Model):
    _name = 'product.catalog'
    _inherit = ['mail.thread']
    _description = 'Product Catalog Generated'
    _order = 'create_date desc,id desc'

    name = fields.Char("Name")
    datas = fields.Binary(string='File Content')
    catalog_name=fields.Char("Catalog Name")
    store_fname = fields.Char('Stored Filename')
    categories = fields.Many2many('product.category', string='Categories')

    def action_download(self):
        """Method used for download catalog file"""
        return{
            'name': 'Product Catalog.pdf',
            'type': 'ir.actions.act_url',
            'url': 'web/content/?model=product.catalog&field=datas&download=true&id=%s&filename=%s' % (self.id, self.store_fname),
            'target': 'self',
        }

    def action_send_by_email(self):
        """ Open a window to compose an email, with the edi invoice template
            message loaded by default
        """
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        try:
            template_id = ir_model_data._xmlid_to_res_id('sh_product_catalog_generator.email_template_edi_product_catalog', raise_if_not_found=False)
        except ValueError:
            template_id = False
        attachment_id = self.env['ir.attachment'].sudo().search(
            [('res_id', '=', self.id)], limit=1)
        ctx = {
            'default_model': 'product.catalog',
            'default_res_id': self.ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'default_partner_id': 1,
            'default_attachment_ids': [(6, 0, attachment_id.ids)],
            'force_email': True
        }
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }
