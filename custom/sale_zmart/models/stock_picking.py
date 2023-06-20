import base64
import qrcode
import io
from odoo import models, fields,api

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    shipping_type = fields.Selection(
        related = 'sale_id.shipping_type', 
        string = "Shipping type"
    )
    shipping_name_company = fields.Many2one(
        related = 'sale_id.shipping_name_company'
    )
    shipping_method = fields.Selection(
        [
            ("prepaid", "Prepaid"),
            ("free", "Free"),
            ("collect_at_destination", "Collect at Destination"),
        ],
        related = "sale_id.shipping_method",
        default = "free",
        store = True
    )
    packing_factor = fields.Char(
        store = "True"
    )
    sequence_code = fields.Char(
        related = 'picking_type_id.sequence_code'
    )
    guide = fields.Char(
        readonly = False
    )
    user_vend_id = fields.Many2one(
        related = "sale_id.user_id"
    )
    user_pick_id = fields.Many2one(
        'res.users', 
        default = lambda self: self.env.user
    )
    user_pack_id = fields.Many2one(
        'res.users', 
        default = lambda self: self.env.user
    )
    user_out_id = fields.Many2one(
        'res.users', 
        default = lambda self: self.env.user
    )
    package_qty = fields.Integer(
        "Package Quantity", 
        help = "Quantity of packages used in the picking"
    )
    qr_code = fields.Binary(
        string = 'Código QR', 
        compute = '_compute_qr_code'
    )
    
    @api.depends('name')
    def _compute_qr_code(self):
        for record in self:
            # Generar el código QR
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
            qr.add_data(record.name)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            # Convertir la imagen a base64
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            qr_image = base64.b64encode(buffer.getvalue())

            # Actualizar el campo binario con el código QR
            record.qr_code = qr_image
    def print_label(self):
        return self.env.ref('sale_zmart.action_print_label').report_action(self)
    