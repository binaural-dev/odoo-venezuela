# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, exceptions, _
from odoo.exceptions import Warning, UserError
import tempfile
import binascii
import logging

_logger = logging.getLogger(__name__)

try:
    import xlrd
except ImportError:
    _logger.debug('Cannot `import xlrd`.')


class importLotWizard(models.TransientModel):
    _name = 'import.lot.wizard'
    _description = "Import Lot/Serial No Single Product"

    select_lot = fields.Selection([('serial', 'Serial No'), ('lot', 'Lot No')], string="Selection", default='serial')
    lot_file = fields.Binary(string="Select File")
    stock_move_id = fields.Many2one('stock.move')

    sample_option = fields.Selection([('lot_serial', 'Serial No'), ('lot', 'Lot No')], string='Sample Type',
                                     default='lot')
    down_samp_file = fields.Boolean(string='Download Sample Files')

    def import_lots(self):
        if not self.lot_file:
            raise UserError(_("Please upload file first."))
        try:
            fp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            fp.write(binascii.a2b_base64(self.lot_file))
            fp.seek(0)
            values = {}
            workbook = xlrd.open_workbook(fp.name)
            sheet = workbook.sheet_by_index(0)
        except Exception:
            raise UserError(_("Invalid file"))
        res = False
        tot = 0.0
        move_lines = self.env['stock.move.line'].search([('move_id', '=', self.stock_move_id.id)])
        move_lines.unlink()
        move_active_id = self.env[self._context.get('active_model')].browse(self._context.get('active_id'))
        if self.select_lot == 'serial':
            if sheet.nrows - 1 > move_active_id.product_uom_qty:
                raise UserError(_("Your file contains more quantity then initial demand."))
        else:
            for row_no in range(sheet.nrows):
                if row_no <= 0:
                    fields = list(map(lambda row: row.value.encode('utf-8'), sheet.row(row_no)))
                else:
                    line = list(
                        map(lambda row: isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value),
                            sheet.row(row_no)))
                    if len(line) == 2:
                        tot += float(line[1])
                    else:
                        raise UserError(
                            _("Format of excel file is inappropriate, Please provide File with proper format."))
            if tot > move_active_id.product_uom_qty:
                raise UserError(_("Your file contains more quantity then initial demand."))
        for row_no in range(sheet.nrows):
            if row_no <= 0:
                fields = list(map(lambda row: row.value.encode('utf-8'), sheet.row(row_no)))
            else:
                try:
                    line = list(
                        map(lambda row: isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value),
                            sheet.row(row_no)))
                    if self.select_lot == 'serial':

                        if len(line) == 1:
                            number = line[0]
                            if number:
                                number = number.split(".")
                                number = number[0]

                            values.update({'lot': number})
                        else:
                            raise UserError(
                                _("Format of excel file is inappropriate, Please provide File with proper format."))
                    else:
                        if len(line) == 2:
                            number = line[0]
                            if number:
                                number = number.split(".")
                                number = number[0]
                            values.update({'lot': number, 'qty': line[1]})
                        else:
                            raise UserError(
                                _("Format of excel file is inappropriate, Please provide File with proper format."))
                    res = self.create_lot_line(values)
                except IndexError:
                    raise UserError(_("You have selected wrong option"))
        view = self.env.ref('stock.view_stock_move_operations')
        stock_pack_id = self.stock_move_id
        if stock_pack_id:
            stock_pack_id.picking_id.write({'state': 'assigned'})
            ctx = dict(
                stock_pack_id.env.context,
                show_lots_m2o=stock_pack_id.has_tracking != 'none' and (
                        stock_pack_id.picking_type_id.use_existing_lots or stock_pack_id.state == 'done' or stock_pack_id.origin_returned_move_id.id),
                # able to create lots, whatever the value of ` use_create_lots`.
                show_lots_text=stock_pack_id.has_tracking != 'none' and stock_pack_id.picking_type_id.use_create_lots and not stock_pack_id.picking_type_id.use_existing_lots and stock_pack_id.state != 'done' and not stock_pack_id.origin_returned_move_id.id,
                show_source_location=stock_pack_id.location_id.child_ids,
                show_destination_location=stock_pack_id.location_dest_id.child_ids,
                show_package=not stock_pack_id.location_id.usage == 'supplier',
                show_reserved_quantity=stock_pack_id.state != 'done',
            )

            ctx.update({'raise-exception': False})

            return {
                'name': _('Detailed Operations'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'stock.move',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': stock_pack_id.id,
                'context': ctx
            }
        else:
            return res

    def create_lot_line(self, values):
        list_lot = []
        lot = values.get('lot')
        stock_pack_id = self.env['stock.move'].browse(self._context.get('active_id'))

        if self.select_lot == 'lot' or stock_pack_id.product_id.tracking == 'lot':
            if stock_pack_id.picking_type_id.code == 'incoming' or stock_pack_id.picking_type_id.code == 'internal':
                create_lot = stock_pack_id.picking_type_id.use_create_lots
                existing_lot = stock_pack_id.picking_type_id.use_existing_lots
                if not existing_lot and create_lot:
                    lot_vals = {
                        'product_id': stock_pack_id.product_id.id,
                        'picking_id': stock_pack_id.picking_id.id,
                        'qty_done': values.get('qty'),
                        'move_id': stock_pack_id.id,
                        'lot_name': values.get('lot'),
                        'product_uom_id': stock_pack_id.product_id.uom_id.id,
                        'location_id': stock_pack_id.picking_id.location_id.id,
                        'location_dest_id': stock_pack_id.picking_id.location_dest_id.id,
                    }
                    self.env['stock.move.line'].with_context({'raise-exception': False}).create(lot_vals)
                elif existing_lot:
                    lot_id = self.find_lot(values.get('lot'), stock_pack_id.id)
                    lot_vals = {
                        'lot_id': lot_id.id,
                        'product_id': lot_id.product_id.id,
                        'picking_id': stock_pack_id.picking_id.id,
                        'qty_done': values.get('qty') or 1,
                        'move_id': stock_pack_id.id,
                        'lot_name': lot_id.name,
                        'product_uom_id': lot_id.product_id.uom_id.id,
                        'location_id': stock_pack_id.picking_id.location_id.id,
                        'location_dest_id': stock_pack_id.picking_id.location_dest_id.id,
                    }
                    self.env['stock.move.line'].with_context({'raise-exception': False}).create(lot_vals)
        else:
            if lot in list_lot:
                raise UserError('You have already mentioned this lot name in another line')
            else:
                if stock_pack_id.picking_id.picking_type_id.code == 'incoming' or stock_pack_id.picking_type_id.code == 'internal':
                    create_lot = stock_pack_id.picking_type_id.use_create_lots
                    existing_lot = stock_pack_id.picking_type_id.use_existing_lots
                    if not existing_lot and create_lot:
                        self.env['stock.move.line'].with_context({'raise-exception': False}).create({
                            'qty_done': 1,
                            'product_id': stock_pack_id.product_id.id,
                            'lot_name': values.get('lot'),
                            'picking_id': stock_pack_id.picking_id.id,
                            'product_uom_id': stock_pack_id.product_id.uom_id.id,
                            'move_id': stock_pack_id.id,
                            'location_id': stock_pack_id.picking_id.location_id.id,
                            'location_dest_id': stock_pack_id.picking_id.location_dest_id.id,

                        })
                    elif existing_lot:
                        lot_id = self.find_lot(values.get('lot'), stock_pack_id.id)
                        res = self.env['stock.move.line'].with_context({'raise-exception': False}).create({
                            'lot_id': lot_id.id,
                            'qty_done': 1,
                            'product_id': lot_id.product_id.id,
                            'lot_name': lot_id.name,
                            'picking_id': stock_pack_id.picking_id.id,
                            'product_uom_id': lot_id.product_id.uom_id.id,
                            'move_id': stock_pack_id.id,
                            'location_id': stock_pack_id.picking_id.location_id.id,
                            'location_dest_id': stock_pack_id.picking_id.location_dest_id.id,
                        })
                        if stock_pack_id.picking_type_id.code == 'internal':
                            res.write({'is_serial': True})

        list_lot.append(lot)

    def find_lot(self, lot, move):
        stock_pack_id = self.env['stock.move'].browse(move)
        lot_details = self.env['stock.lot'].search(
            [('name', '=', lot), ('product_id', '=', stock_pack_id.product_id.id)])

        if not lot_details.id:
            lot_details = self.env['stock.lot'].create({
                'name': lot,
                'product_id': stock_pack_id.product_id.id,
                'product_uom_id': stock_pack_id.product_id.uom_id.id,
                'company_id': stock_pack_id.company_id.id,
            })

        return lot_details

    def download_auto(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/download_document?model=import.lot.wizard&id=%s' % (self.sudo().id),
            'target': 'new',
        }
