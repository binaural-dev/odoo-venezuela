from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.http import request
from odoo.addons.binaural_base_qr.models.qr_code_base import generate_qr_code

class StockLot(models.Model):
    _inherit = "stock.lot"
    
    file_data = fields.Binary(string='File Data')  # Cambiado de document2 a file_data
    file_name = fields.Char(string='File Name')  # Cambiado de document_name a file_name
    attachment_id = fields.Many2one('ir.attachment', string='Attached Document')  # Cambiado de document a attachment_id
    attachment_url = fields.Char(string='Attachment URL')  # Cambiado de document_urls a attachment_url
    attachment_url2 = fields.Char(string='Attachment URL')  # Cambiado de document_urls a attachment_url
    base_url = fields.Char(string='URL')
    
    @api.onchange('file_data', 'file_name')
    def _onchange_file_data(self):
        if not self.file_name:  # Verifica si file_name está vacío
            self.file_name = "Documento"  # Asigna un nombre predeterminado

        if self.file_data and self.file_name:
            # Crear el attachment
            attachment = self.env['ir.attachment'].create({
                'name': self.file_name,
                'type': 'binary',
                'datas': self.file_data,
                'res_model': 'stock.lot',
                'res_id': self.id,
                'public': True,
            })
            self.attachment_id = attachment.id  # Asocia el attachment al campo Many2one
            self.attachment_url = attachment.local_url  # Guarda la URL del attachment
            
            # Usa self para acceder a los campos de instancia
            base_url = self.env['ir.config_parameter'].get_param('web.base.url')
            full_url = base_url + self.attachment_url
            self.base_url = full_url
            self._generate_qr_code()
        else:
            self.attachment_url = ''
            self.base_url = ''
            
    qr_image = fields.Binary("QR Code", compute='_generate_qr_code')
    
    def write(self, vals):
        if 'file_data' in vals and self.file_data and not self.user_has_groups('cadipa_farming.group_edit_document_lot'):
            raise UserError(_("You cannot edit the document after creation."))
        return super().write(vals)

    def _generate_qr_code(self):
        base_url = self.base_url
        self.qr_image = generate_qr_code(base_url)