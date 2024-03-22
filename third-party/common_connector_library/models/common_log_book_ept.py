# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api


class CommonLogBookEpt(models.Model):
    _name = "common.log.book.ept"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = 'id desc'
    _description = "Common log book Ept"

    name = fields.Char(readonly=True)
    type = fields.Selection([('import', 'Import'), ('export', 'Export')], string="Operation")
    module = fields.Selection([('amazon_ept', 'Amazon Connector'),
                               ('woocommerce_ept', 'Woocommerce Connector'),
                               ('shopify_ept', 'Shopify Connector'),
                               ('magento_ept', 'Magento Connector'),
                               ('bol_ept', 'Bol Connector'),
                               ('ebay_ept', 'Ebay Connector'),
                               ('amz_vendor_central', 'Amazon Vendor Central'),
                               ('tpw_ept', '3PL Connector'),
                               ('walmart_ept', 'Walmart Connector')])
    active = fields.Boolean(default=True)
    log_lines = fields.One2many('common.log.lines.ept', 'log_book_id')
    message = fields.Text()
    model_id = fields.Many2one("ir.model", help="Model Id", string="Model")
    res_id = fields.Integer(string="Record ID", help="Process record id")
    attachment_id = fields.Many2one('ir.attachment', string="Attachment")
    file_name = fields.Char()
    sale_order_id = fields.Many2one(comodel_name='sale.order', string='Sale Order')

    @api.model_create_multi
    def create(self, vals_list):
        """ To generate a sequence for a common logbook.
            @param : vals : Dictionary of common log book create.
        """
        for vals in vals_list:
            seq = self.env['ir.sequence'].next_by_code('common.log.book.ept') or '/'
            vals['name'] = seq
        return super(CommonLogBookEpt, self).create(vals_list)

    def create_common_log_book_ept(self, **kwargs):
        """
        This method is use to create a log book.
        @param : **kwargs, Pass the argument like,
        log_book = self.env['common.log.book.ept'].create_common_log_book_ept (module='shopify_ept',
        model_name='sale.order',type='import')
        """
        values = {}
        for key, value in kwargs.items():
            if hasattr(self, key):
                values.update({key: value})
        if kwargs.get('model_name'):
            model = self._get_model_id(kwargs.get('model_name'))
            values.update({'model_id': model.id})
        return self.create(values)

    def _get_model_id(self, model_name):
        """
        It is use to get the model id
        @param :  model_name : Name of the model
        """
        model_id = self.env['ir.model']
        return model_id.sudo().search([('model', '=', model_name)])
