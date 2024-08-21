# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, exceptions , models, _
from odoo.exceptions import Warning, ValidationError
import tempfile
import binascii
import xlrd
import logging
import io
from tempfile import TemporaryFile

_logger = logging.getLogger(__name__)

try:
    import base64
except ImportError:
    _logger.debug('Cannot `import base64`.')

try:
    import csv
except ImportError:
    _logger.debug('Cannot `import csv`.')

try:
    import xlwt
except ImportError:
    _logger.debug('Cannot `import xlwt`.')    

try:
    import cStringIO
except ImportError:
    _logger.debug('Cannot `import cStringIO`.')        

try:
    import xlrd
except ImportError:
    _logger.debug('Cannot `import xlrd`.')

class import_lot_wizard(models.TransientModel):

    _name = 'import.lot.multi.wizard'

    import_option = fields.Selection([('csv', 'CSV File'),('xls', 'XLS File')],string='Select',default='csv')
    select_lot = fields.Selection([('serial','Serial No'),('lot','Lot No')],string="Selection",default='serial')
    lot_file = fields.Binary(string="Select File")
    product_based_on = fields.Selection([('name','Name'),('code','Code'),('barcode','Barcode')] , string = "Import Product Based On" ,required = True , default = "name")

    sample_option = fields.Selection([('csv', 'CSV'),('xls', 'XLS')],string='Sample Type',default='csv')
    down_samp_file = fields.Boolean(string='Download Sample Files')



    def import_bulk_of_lots(self):
        """Load Inventory data from the CSV file."""
        main_qty = 0
        if not self.lot_file:
            raise ValidationError(_("Please upload file first."))
        if not self.import_option:
            raise ValidationError(_("Please Select which file you want to import."))
        if self.import_option == 'csv':
            if self.select_lot == 'serial':
                keys = ['serial no', 'name']
            else:
                keys = ['serial no', 'quantity', 'name']

            move_active_id = self.env[self._context.get('active_model')].browse(self._context.get('active_id'))
            try:
                csv_data = base64.b64decode(self.lot_file)
                data_file = io.StringIO(csv_data.decode("utf-8"))
                data_file.seek(0)
                file_reader = []
                sale_ids = []
                csv_reader = csv.reader(data_file, delimiter=',')
                file_reader.extend(csv_reader)
            except Exception:
                raise exceptions.ValidationError(_("Invalid file!"))
            values = {}
            for move in move_active_id.move_ids_without_package:
                if self.select_lot == "serial":
                    if move.product_id.tracking == "serial":
                        for line in move.move_line_ids:
                            line.unlink()
                elif self.select_lot == "lot":
                    if move.product_id.tracking == "lot":
                        for line in move.move_line_ids:
                            line.unlink()
            for picking in move_active_id.move_ids_without_package:
                serial_tot = 0.0
                tot = 0.0
                for i in range(len(file_reader)):
                    field = list(map(str, file_reader[i]))
                    values = dict(zip(keys, field))
                    if values:
                        if i == 0:
                            continue
                        else:
                            if self.product_based_on == "name":
                                product_id = self.env['product.product'].search([('name','=',values.get('name'))])
                            elif self.product_based_on == "code":
                                product_id = self.env['product.product'].search([('default_code','=',values.get('name'))])
                            elif self.product_based_on == "barcode":
                                product_id = self.env['product.product'].search([('barcode','=',values.get('name'))])
                            else:
                                raise ValidationError(_("Your file contains wrong product, please enter valid product details."))
                            if product_id:
                                product_id = product_id[0]
                            if product_id.id == False:
                                raise ValidationError(_("Your file contains wrong product, please enter valid product details."))
                                
                            if self.select_lot == "serial":
                                if move_active_id.id:
                                    if self.product_based_on == "name":
                                        if values.get('name') == picking.product_id.name:
                                            serial_tot += float(1.0)
                                            main_qty = picking.product_uom_qty
                                    if self.product_based_on == "code":
                                        if values.get('name') == picking.product_id.default_code:
                                            main_qty = picking.product_uom_qty
                                            serial_tot += float(1.0)
                                    if self.product_based_on == "barcode":
                                        if values.get('name') == picking.product_id.barcode:
                                            main_qty = picking.product_uom_qty
                                            serial_tot += float(1.0)
                                if serial_tot > main_qty:
                                    raise ValidationError(_("Your file contains more quantity then initial demand.")) 
                            else:
                                if move_active_id.id:
                                    if values.get('quantity'):
                                        quant = float(values.get('quantity'))
                                    else:
                                        quant = False
                                    if self.product_based_on == "name":
                                        if values.get('name') == picking.product_id.name:
                                            tot += quant
                                            main_qty = picking.product_uom_qty
                                    if self.product_based_on == "code":
                                        if values.get('name') == picking.product_id.default_code:
                                            tot += quant
                                            main_qty = picking.product_uom_qty
                                    if self.product_based_on == "barcode":
                                        if values.get('name') == picking.product_id.barcode:
                                            tot += quant
                                            main_qty = picking.product_uom_qty
                                if tot > main_qty:
                                    raise ValidationError(_("Your file contains more quantity then initial demand."))
            for picking in move_active_id.move_ids_without_package:
                for i in range(len(file_reader)):
                    field = list(map(str, file_reader[i]))
                    values = dict(zip(keys, field))
                    if values:
                        if i == 0:
                            continue
                        else:
                            try:
                                if self.select_lot == 'serial':
                                    if move_active_id.id:
                                        if self.product_based_on == "name":
                                            if values.get('name') == picking.product_id.name:
                                                values.update({'lot':values.get('serial no'),
                                                                'move' : picking.id,
                                                                'product_id' : picking.product_id.id
                                                                         })
                                                res = self.create_lot_line(values)
                                        if self.product_based_on == "code":
                                            if values.get('name') == picking.product_id.default_code:
                                                values.update({'lot':values.get('serial no'),
                                                                'move' : picking.id,
                                                                'product_id' : picking.product_id.id
                                                                         })
                                                res = self.create_lot_line(values)
                                        if self.product_based_on == "barcode":
                                            if values.get('name') == picking.product_id.barcode:
                                                values.update({'lot':values.get('serial no'),
                                                                'move' : picking.id,
                                                                'product_id' : picking.product_id.id
                                                                         })
                                                res = self.create_lot_line(values)
                                    else:
                                        raise ValidationError(_("Format of excel/csv file is inappropriate, Please provide File with proper format.")) 
                                    
                                else:
                                    if move_active_id.id:
                                        if self.product_based_on == "name":
                                            if values.get('name') == picking.product_id.name:                        
                                                values.update({'lot':values.get('serial no'),
                                                                'qty':values.get('quantity'),
                                                                'move':picking.id,
                                                                'product_id':picking.product_id.id
                                                                })
                                                res = self.create_lot_line(values)
                                        if self.product_based_on == "code":
                                            if values.get('name') == picking.product_id.default_code:                        
                                                values.update({'lot':values.get('serial no'),
                                                                'qty':values.get('quantity'),
                                                                'move':picking.id,
                                                                'product_id':picking.product_id.id
                                                                })
                                                res = self.create_lot_line(values)
                                        if self.product_based_on == "barcode":
                                            if values.get('name') == picking.product_id.barcode:                        
                                                values.update({'lot':values.get('serial no'),
                                                                'qty':values.get('quantity'),
                                                                'move':picking.id,
                                                                'product_id':picking.product_id.id
                                                                })
                                                res = self.create_lot_line(values)
                                    else:
                                        raise ValidationError(_("Format of excel/csv file is inappropriate, Please provide File with proper format."))
                            except IndexError:
                                raise ValidationError(_("You have selected wrong option"))                            
        else:
            try:
                fp = tempfile.NamedTemporaryFile(delete=False,suffix=".xlsx")
                fp.write(binascii.a2b_base64(self.lot_file))
                fp.seek(0)
                values = {}
                workbook = xlrd.open_workbook(fp.name)
                sheet = workbook.sheet_by_index(0)
            except Exception:
                raise exceptions.ValidationError(_("Invalid file"))


            res = False
            main_qty = 0
            move_active_id = self.env[self._context.get('active_model')].browse(self._context.get('active_id'))
            for move in move_active_id.move_ids_without_package:
                if self.select_lot == 'serial':
                    for line in move.move_line_ids:
                        if move.product_id.tracking == "serial":
                            line.unlink()
                elif self.select_lot == 'lot':
                    for line in move.move_line_ids:
                        if move.product_id.tracking == "lot":
                            line.unlink()                        
            if self.select_lot == 'serial':
                for picking in move_active_id.move_ids_without_package:
                    serial_tot = 0.0
                    for row_no in range(sheet.nrows):
                        if row_no <= 0:
                            fields = list(map(lambda row:row.value.encode('utf-8'), sheet.row(row_no)))
                        else:
                            line = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet.row(row_no)))
                            if self.product_based_on == "name":
                                product_id = self.env['product.product'].search([('name','=',line[1])])
                            elif self.product_based_on == "code":
                                product_id = self.env['product.product'].search([('default_code','=',line[1].split(".")[0])])
                            elif self.product_based_on == "barcode":
                                product_id = self.env['product.product'].search([('barcode','=',line[1].split(".")[0])])
                            else:
                                raise ValidationError(_("Your file contains wrong product details , please enter valid product details."))
                            if product_id:
                                product_id = product_id[0]
                            if product_id.id == False:
                                raise ValidationError(_("Your file contains wrong product, please enter valid product details."))

                            if move_active_id.id:
                                if self.product_based_on == "name":
                                    if line[1] == picking.product_id.name:
                                        serial_tot += float(1.0)
                                        main_qty = picking.product_uom_qty
                                if self.product_based_on == "code":
                                    if line[1].split(".")[0] == picking.product_id.default_code:
                                        main_qty = picking.product_uom_qty
                                        serial_tot += float(1.0)
                                if self.product_based_on == "barcode":
                                    if line[1].split(".")[0] == picking.product_id.barcode:
                                        main_qty = picking.product_uom_qty
                                        serial_tot += float(1.0)
                            if serial_tot > main_qty:
                                raise ValidationError(_("Your file contains more quantity then initial demand."))
            else:
                for picking in move_active_id.move_ids_without_package:
                    tot = 0.0
                    for row_no in range(sheet.nrows):
                        if row_no <= 0:
                            fields = list(map(lambda row:row.value.encode('utf-8'), sheet.row(row_no)))
                        else:
                            line = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet.row(row_no)))
                            if len(line) == 3:
                                if self.product_based_on == "name":
                                    product_id = self.env['product.product'].search([('name','=',line[2])])
                                elif self.product_based_on == "code":
                                    product_id = self.env['product.product'].search([('default_code','=',line[2].split(".")[0])])
                                elif self.product_based_on == "barcode":
                                    product_id = self.env['product.product'].search([('barcode','=',line[2].split(".")[0])])
                                else:
                                    raise ValidationError(_("Your file contains wrong product details , please enter valid product details."))
                                if product_id:
                                    product_id = product_id[0]
                                if product_id.id == False:
                                    raise ValidationError(_("Your file contains wrong product, please enter valid product details."))
                                if move_active_id.id:
                                    if line[1]:
                                        quant = float(line[1])
                                    else:
                                        quant = False
                                    if self.product_based_on == "name":
                                        if line[2].split(".")[0] == picking.product_id.name:
                                            tot += quant
                                            main_qty = picking.product_uom_qty
                                    if self.product_based_on == "code":
                                        if line[2].split(".")[0] == picking.product_id.default_code:
                                            tot += quant
                                            main_qty = picking.product_uom_qty
                                    if self.product_based_on == "barcode":
                                        if line[2].split(".")[0] == picking.product_id.barcode:
                                            tot += quant
                                            main_qty = picking.product_uom_qty
                                if tot > main_qty:
                                    raise ValidationError(_("Your file contains more quantity then initial demand."))
                            else:
                                raise ValidationError(_("Your file contains wrong details, please refer demo file.."))
            for row_no in range(sheet.nrows):

                if row_no <= 0:
                    fields = list(map(lambda row:row.value.encode('utf-8'), sheet.row(row_no)))
                else:
                    try:
                        line = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet.row(row_no)))
                        if self.select_lot == 'serial':
                            if len(line)==2:
                                if move_active_id.id:
                                    for picking in move_active_id.move_ids_without_package:
                                        if picking.product_id.tracking == "serial":
                                            if self.product_based_on == "name":
                                                if line[1] == picking.product_id.name:
                                                    values.update({'lot':str(line[0]),
                                                                    'move' : picking.id,
                                                                    'product_id' : picking.product_id.id
                                                                             })
                                                    res = self.create_lot_line(values)
                                            if self.product_based_on == "code":
                                                if line[1].split(".")[0] == picking.product_id.default_code:
                                                    values.update({'lot':str(line[0]),
                                                                    'move' : picking.id,
                                                                    'product_id' : picking.product_id.id
                                                                             })
                                                    res = self.create_lot_line(values)
                                            if self.product_based_on == "barcode":
                                                if line[1].split(".")[0] == picking.product_id.barcode:
                                                    values.update({'lot':str(line[0]),
                                                                    'move' : picking.id,
                                                                    'product_id' : picking.product_id.id
                                                                             })
                                                    res = self.create_lot_line(values)
                            else:
                                raise ValidationError(_("Format of excel/csv file is inappropriate, Please provide File with proper format.")) 
                            
                        else:
                            if len(line)==3:
                                if move_active_id.id:
                                    for picking in move_active_id.move_ids_without_package:
                                        if picking.product_id.tracking == "lot":
                                            if self.product_based_on == "name":
                                                if line[2].split(".")[0] == picking.product_id.name:                        
                                                    values.update({'lot':str(line[0]),
                                                                    'qty':line[1],
                                                                    'move':picking.id,
                                                                    'product_id':picking.product_id.id
                                                                    })
                                                    res = self.create_lot_line(values)
                                            if self.product_based_on == "code":
                                                if line[2].split(".")[0] == picking.product_id.default_code:                        
                                                    values.update({'lot':str(line[0]),
                                                                    'qty':line[1],
                                                                    'move':picking.id,
                                                                    'product_id':picking.product_id.id
                                                                    })
                                                    res = self.create_lot_line(values)
                                            if self.product_based_on == "barcode":
                                                if line[2].split(".")[0] == picking.product_id.barcode:
                                                    values.update({'lot':str(line[0]),
                                                                    'qty':line[1],
                                                                    'move':picking.id,
                                                                    'product_id':picking.product_id.id
                                                                    })
                                                    res = self.create_lot_line(values)
                            else:
                                raise ValidationError(_("Format of excel/csv file is inappropriate, Please provide File with proper format."))
                    except IndexError:
                        raise ValidationError(_("You have selected wrong option"))


    def create_lot_line(self,values):
        list_lot=[]
        lot=values.get('lot')
        stock_pack_id=self.env['stock.move'].browse(values.get('move'))
        if self.select_lot == 'lot' or stock_pack_id.product_id.tracking == 'lot':
            if stock_pack_id.picking_type_id.code == 'incoming' or stock_pack_id.picking_type_id.code == 'internal':
                if stock_pack_id.picking_id.create_lot:
                    self.env['stock.move.line'].with_context({'raise-exception':False}).create({
                                                                'qty_done':values.get('qty'),
                                                                'product_id':stock_pack_id.product_id.id,
                                                                'lot_name':values.get('lot').split(".")[0],
                                                                'picking_id':stock_pack_id.picking_id.id,
                                                                'product_uom_id':stock_pack_id.product_id.uom_id.id,
                                                                'move_id':stock_pack_id.id,
                                                                'location_id':stock_pack_id.picking_id.location_id.id,
                                                                'location_dest_id':stock_pack_id.picking_id.location_dest_id.id,
                                                                })
                elif stock_pack_id.create_exist_lot:                 
                    lot_id =self.find_lot(values.get('lot') , stock_pack_id.id)
                    lot_vals = {'lot_id':lot_id.id,
                                'product_id':lot_id.product_id.id,
                                'picking_id':stock_pack_id.picking_id.id,
                                'qty_done':values.get('qty'),
                                'move_id':stock_pack_id.id,
                                'lot_name':lot_id.name,
                                'product_uom_id':lot_id.product_id.uom_id.id,
                                'location_id':stock_pack_id.picking_id.location_id.id,
                                'location_dest_id':stock_pack_id.picking_id.location_dest_id.id,
                    }
                    self.env['stock.move.line'].with_context({'raise-exception':False}).create(lot_vals)
        else:
            if lot in list_lot:
                raise ValidationError('You have already mentioned this lot name in another line')
            else:
                if stock_pack_id.picking_id.picking_type_id.code == 'incoming' or stock_pack_id.picking_type_id.code == 'internal':
                    if stock_pack_id.picking_id.create_lot:
                        self.env['stock.move.line'].with_context({'raise-exception':False}).create({
                                                                    'qty_done':1,
                                                                    'product_id':stock_pack_id.product_id.id,
                                                                    'lot_name':values.get('lot').split(".")[0],
                                                                    'picking_id':stock_pack_id.picking_id.id,
                                                                    'product_uom_id':stock_pack_id.product_id.uom_id.id,
                                                                    'move_id':stock_pack_id.id,
                                                                    'location_id':stock_pack_id.picking_id.location_id.id,
                                                                    'location_dest_id':stock_pack_id.picking_id.location_dest_id.id,
                                                                    })
                    elif stock_pack_id.create_exist_lot:                    
                        lot_id =self.find_lot(values.get('lot'),stock_pack_id.id)
                        self.env['stock.move.line'].with_context({'raise-exception':False}).create({'lot_id':lot_id.id,
                                                                'qty_done':1,
                                                                'product_id':lot_id.product_id.id,
                                                                'lot_name':lot_id.name,
                                                                'picking_id':stock_pack_id.picking_id.id,
                                                                'product_uom_id':lot_id.product_id.uom_id.id,
                                                                'lot_name':lot_id.name,
                                                                'move_id':stock_pack_id.id,
                                                                'location_id':stock_pack_id.picking_id.location_id.id,
                                                                'location_dest_id':stock_pack_id.picking_id.location_dest_id.id,
                                                                })

        list_lot.append(lot)

    def find_lot(self,lot , move):
        stock_pack_id=self.env['stock.move'].browse(move)
        lot_details = self.env['stock.lot'].search([('name','=', lot), ('product_id','=',stock_pack_id.product_id.id)])

        if not lot_details.id:         
            lot_details=self.env['stock.lot'].create({
                                                           'name':lot,
                                                           'product_id':stock_pack_id.product_id.id,
                                                           'product_uom_id':stock_pack_id.product_id.uom_id.id,
                                                           'company_id' : stock_pack_id.company_id.id
                                                           })
        return lot_details
    
    
    
    
    def download_auto(self):
        return {
             'type' : 'ir.actions.act_url',
             'url': '/web/binary/download_document1?model=import.lot.multi.wizard&id=%s'%(self.sudo().id),
             'target': 'new',
             }

    

class stock_picking_inherited(models.Model):
    _inherit = 'stock.picking'

    create_exist_lot = fields.Boolean(string="Import Lot/serial with existing lot",compute = "_check_import_lot_serial" , default = False)
    create_lot = fields.Boolean(string="Import New Lot/serial",compute = "_check_import_lot_serial" , default = False)

    @api.depends('picking_type_id.use_create_lots' , 'picking_type_id.use_existing_lots')
    def _check_import_lot_serial(self):
        if self.picking_type_id.use_create_lots and self.picking_type_id.use_existing_lots:
            self.update({
                'create_exist_lot': True,
                'create_lot' : False
                })
        elif self.picking_type_id.use_create_lots and not self.picking_type_id.use_existing_lots:
            self.update({
                'create_exist_lot': False,
                'create_lot' : True
                })
        else:
            self.update({
                'create_exist_lot': False,
                'create_lot' : False
                }) 


    def open_multi_wizard(self):
        view = self.env.ref('import_lot_serial_no_with_multiple_product.picking_lot_wizard_view')
        return {
            'name': _('Import Lots/Serial'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'import.lot.multi.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
