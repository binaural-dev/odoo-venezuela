from odoo import _, fields, models, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    from_picking_line = fields.Boolean(string="From Picking", default=False)

    # TODO: Validar que solo se puedan agregar productos de tipo servicio cuando la factura proviene de un picking
    #
    # Problema: la validación comentada además de no permitir agregar productos que no sean de tipo servicio en la factura,
    #           también ocasiona que el código base de Odoo no pueda llevar a cabo ciertas acciones, por lo que corta el flujo.
    #
    #           Idealmente la validación solo afecta a las interacciones del usuario desde la factura y no todo el resto de código
    #           que haga uso de create()
    #
    # @api.model
    # def create(self, vals):
    #     move = self.env['account.move'].browse(vals.get('move_id'))
    #     if move.from_picking:
    #         product = self.env['product.product'].browse(vals.get('product_id'))
    #         if product and product.type != 'service':
    #             raise ValidationError(_("You can only add service products to an invoice created from a picking."))
    #     return super(AccountMoveLine, self).create(vals)
