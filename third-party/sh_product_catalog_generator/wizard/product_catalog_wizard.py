# Copyright (C) Softhealer Technologies.

from odoo import models, fields, api
from odoo.exceptions import UserError
import base64
from PyPDF2 import PdfFileWriter, PdfFileReader
import io
import xlwt
from io import BytesIO
from PIL import Image
import os


class GenerateProductCatalogWizard(models.TransientModel):

    _name = 'product.catalog.wizard'
    _description = 'Product Catalog Wizard'

    name = fields.Char('Catalog Name', required=True)
    catalog_type = fields.Selection(
        [('product', 'Product'), ('category', 'Category')], default='product', string="Catalog Type")
    product_ids = fields.Many2many('product.product', string='Products')
    category_ids = fields.Many2many('product.category', string='Categories')
    price = fields.Boolean(string='Price')
    pricelist_id = fields.Many2one('product.pricelist', 'Pricelist')
    image = fields.Boolean(string='Image')
    image_size = fields.Selection([('small', 'Small'), ('medium', 'Medium'), (
        'large', 'Large')], default='small', string='Image Size')
    description = fields.Boolean('Description')
    product_link = fields.Boolean('Product Link')
    style = fields.Selection([('style_1', 'Style 1'), ('style_2', 'Style 2'), ('style_3', 'Style 3'), (
        'style_4', 'Style 4'), ('style_5', 'Style 5')], default='style_1', string='Style')
    int_ref = fields.Boolean('Internal Reference')
    style_box = fields.Selection([('2', '2 box per row'), ('3', '3 box per row'), (
        '4', '4 box per row')], default='2', string='Print Box Per Row')
    break_page = fields.Boolean(string='Break Page')
    break_page_after_products = fields.Integer(
        string='Break page after products', default=1)
    currency_id = fields.Many2one('res.currency', 'Currency', required=True)
    default_before_page = fields.Many2one(
        'default.before.pages', string="Before Page")
    default_after_page = fields.Many2one(
        'default.after.pages', string="After Page")
    sh_add_uom_catalog = fields.Boolean('Print UOM ?')
    sh_print_category_name = fields.Boolean('Print Category ?')
    sh_price_decimal_places = fields.Integer('Price Decimal Places', default=1)

    @api.constrains('sh_price_decimal_places')
    def _check_sh_decimal_places(self):
        """Raised warning when decimal places will be 0"""
        if self.sh_price_decimal_places <= 0:
            raise UserError('You can not set Decimal Places as Zero or -ve')

    @api.onchange('style')
    def onchange_style(self):
        """set all configurable fields values based on catalog style 2"""
        if self.style == 'style_2':
            self.price = True
            self.image = True
            self.int_ref = True
            self.product_link = True
            self.description = True
        if self.style == 'style_1':
            self.break_page = False

    @api.model
    def default_get(self, fields_list):
        """Set Default Currency"""
        res = super(GenerateProductCatalogWizard,
                    self).default_get(fields_list)
        res.update({
            'currency_id': self.env.company.currency_id.id,
        })
        return res

    @api.onchange('currency_id')
    def onchange_currency(self):
        """Fetch and display pricelist based on currency selected"""
        self.pricelist_id = False
        price_list = self.env['product.pricelist'].sudo().search(
            [('currency_id', '=', self.currency_id.id)]).ids
        domain = {'pricelist_id': [('id', 'in', price_list)]}
        return {'domain': domain}

    @api.onchange('price')
    def onchange_price(self):
        """Raised Usererror if selected style 2 then price is required"""
        if self.style == 'style_2' and not self.price:
            raise UserError('Required for style 2')

    @api.onchange('image')
    def onchange_image(self):
        """Raised Usererror if selected style 2 then image is required"""
        if self.style == 'style_2' and not self.image:
            raise UserError('Required for style 2')

    @api.onchange('int_ref')
    def onchange_int_ref(self):
        """Raised Usererror if selected style 2 then int_ref is required"""
        if self.style == 'style_2' and not self.int_ref:
            raise UserError('Required for style 2')

    @api.onchange('product_link')
    def onchange_product_link(self):
        """Raised Usererror if selected style 2 then product link is required"""
        if self.style == 'style_2' and not self.product_link:
            raise UserError('Required for style 2')

    @api.onchange('description')
    def onchange_description(self):
        """Raised Usererror if selected style 2 then description is required"""
        if self.style == 'style_2' and not self.description:
            raise UserError('Required for style 2')

    def print_report(self):
        """Prepared dynamic data from wizard and send it to qweb pdf report abstract method in return pdf file will generate"""
        pdfs = []
        if self.default_before_page:
            pd = self.default_before_page
            datas = base64.b64decode(
                pd.with_context(bin_size=False).before_datas)
            pdfs.append(datas)
        datas = self.read()[0]
        pdf = self.env.ref(
            'sh_product_catalog_generator.product_catalog_report_action').report_action([], data=datas)
        r = self.env['report.sh_product_catalog_generator.product_catalog_doc']
        pdf, _ = self.env['ir.actions.report'].with_context(
            datas)._render_qweb_pdf('sh_product_catalog_generator.product_catalog_report_action', r, datas)
        pdfhttpheaders = [('Content-Type', 'application/pdf'),
                          ('Content-Length', len(pdf))]
        b64_pdf = base64.encodebytes(pdf)
        writer = PdfFileWriter()
        if b64_pdf:
            datas = base64.b64decode(pdf)
            pdfs.append(pdf)
        if self.default_after_page:
            pd1 = self.default_after_page
            datas1 = base64.b64decode(
                pd1.with_context(bin_size=False).after_datas)
            pdfs.append(datas1)
        for document in pdfs:
            reader = PdfFileReader(io.BytesIO(document), strict=False)
            for page in range(0, reader.getNumPages()):
                writer.addPage(reader.getPage(page))
        with io.BytesIO() as _buffer:
            writer.write(_buffer)
            merged_pdf = _buffer.getvalue()
            _buffer.close()
        m_PDf = base64.encodebytes(merged_pdf)
        catalog_id = self.env['product.catalog'].sudo().create({
            'name': self.name + '.pdf',
            'catalog_name': self.name,
            'store_fname': self.name + '.pdf',
            'datas': m_PDf,
        })
        cat_att_id = self.env['ir.attachment'].sudo().create({
            'name': self.name + '.pdf',
            'type': 'binary',
            'datas': m_PDf,
            'res_model': 'product.catalog',
            'res_id': str(catalog_id.id),
        })
        attachment_url = '/web/content/' + \
            str(cat_att_id.id) + '?download=true&filename=' + self.name+'.pdf'
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': attachment_url,
        }

    def print_report_xls(self):
        """Print Catalog XLS report will work only for style 1"""
        datas = self.read()[0]
        workbook = xlwt.Workbook()
        damm = self.env['report.sh_product_catalog_generator.product_catalog_doc']._get_report_values([
        ], data=datas)
        count_header = 0
        count_header_end = 0
        worksheet = workbook.add_sheet('My XLS Report')
        bold_center = xlwt.easyxf(
            'font:height 280,bold True;align: vert center;align: horiz center;'
        )
        bold_header = xlwt.easyxf(
            'font:height 200,bold True;align: vert center;align: horiz center;'
        )
        data_center = xlwt.easyxf(
            'font:height 200;align: vert center;align: horiz center;'
        )
        domain = [('key', '=', 'web.base.url')]
        config = self.env['ir.config_parameter'].sudo().search(domain)
        worksheet.write_merge(1, 2, 5, 8, self.name, bold_center)
        if damm.get('sh_is_location_wise'):
            location = damm.get('location_wise_products')
            worksheet.write_merge(4, 5, 5, 8, *location.keys(), bold_center)

        worksheet.write_merge(7, 7, count_header,
                              count_header_end, 'SR.No.', bold_header)
        if damm.get('int_ref'):
            count_header = count_header_end + 1
            count_header_end = count_header + 1
            worksheet.write_merge(
                7, 7, count_header, count_header_end, 'Internal reference', bold_header)
        count_header = count_header_end + 1
        count_header_end = count_header + 1
        worksheet.write_merge(7, 7, count_header,
                              count_header_end, 'Product Name', bold_header)
        if damm.get('price'):
            count_header = count_header_end + 1
            count_header_end = count_header
            if damm.get('is_secondary_id'):
                worksheet.write_merge(
                    7, 7, count_header, count_header_end, 'Secondary Price', bold_header)
            else:
                worksheet.write_merge(7, 7, count_header,
                                      count_header_end, 'Price', bold_header)
        if damm.get('description'):
            count_header = count_header_end + 1
            count_header_end = count_header + 1
            worksheet.write_merge(7, 7, count_header,
                                  count_header_end, 'Description', bold_header)
        if damm.get('image'):
            count_header = count_header_end + 1
            count_header_end = count_header + 1
            worksheet.write_merge(7, 7, count_header,
                                  count_header_end, 'Image', bold_header)
        sr_count = 0
        line_count = 9
        count_header = 0
        count_header_end = 0
        product_count = 0
        for data in damm['product_dict_list']:
            if damm.get('image'):
                if damm.get('image_size') == 'small':
                    worksheet.row(line_count).height_mismatch = True
                    worksheet.row(line_count).height = 1700
                if damm.get('image_size') == 'medium':
                    worksheet.row(line_count).height_mismatch = True
                    worksheet.row(line_count).height = 3600
                if damm.get('image_size') == 'large':
                    worksheet.row(line_count).height_mismatch = True
                    worksheet.row(line_count).height = 5500
            datap = self.env['product.template'].sudo().search(
                [('id', '=', data['template_id'])])
            product_href = "'%s/shop/product/%s'" % (config.value, datap.id)
            sr_count += 1
            worksheet.write_merge(
                line_count, line_count, count_header, count_header_end, sr_count, data_center)
            if damm.get('int_ref'):
                count_header = count_header_end + 1
                count_header_end = count_header + 1
                worksheet.write_merge(line_count, line_count, count_header,
                                      count_header_end, data['default_code'], data_center)
            count_header = count_header_end + 1
            count_header_end = count_header + 1
            if damm.get('product_link'):
                T = '%s' % (data['name'])
                formula = 'HYPERLINK("{}", "{}")'.format(product_href, T)
                worksheet.write_merge(line_count, line_count, count_header,
                                      count_header_end, xlwt.Formula(formula), data_center)
            else:
                worksheet.write_merge(
                    line_count, line_count, count_header, count_header_end, data['name'], data_center)
            if damm.get('price'):
                count_header = count_header_end + 1
                count_header_end = count_header
                float_price = float(data.get('price'))
                price = format(float_price, '.' +
                               str(self.sh_price_decimal_places)+"f")

                worksheet.write_merge(
                    line_count, line_count, count_header, count_header_end, price, data_center)
            if damm.get('description'):
                count_header = count_header_end + 1
                count_header_end = count_header + 1
                worksheet.write_merge(line_count, line_count, count_header,
                                      count_header_end, data['description'], data_center)
            if damm.get('image'):
                var_data = self.env['product.product'].sudo().search(
                    [('id', '=', data['id'])])
                count_header = count_header_end + 1
                count_header_end = count_header + 1
                if var_data.image_128:
                    product_count += 1
                    parent_dir = '/tmp'
                    image_dir_path = parent_dir + str('/images')
                    is_image_dir_exist = os.path.exists(
                        os.path.join(os.getcwd(), parent_dir, image_dir_path))
                    if not is_image_dir_exist:
                        os.mkdir(image_dir_path)
                    filename = str(var_data.id)
                    if damm.get('image_size') == 'small':
                        im = Image.open(
                            BytesIO(base64.b64decode(var_data.image_128)))
                    if damm.get('image_size') == 'medium':
                        im = Image.open(
                            BytesIO(base64.b64decode(var_data.image_256)))
                    if damm.get('image_size') == 'large':
                        im = Image.open(
                            BytesIO(base64.b64decode(var_data.image_512)))
                    imgext = '.' + Image.MIME[im.format].split('/')[1]
                    filename = filename.replace('/', '')
                    file_path = os.path.join(
                        image_dir_path, filename + imgext)
                    im.save(file_path)
                    img = Image.open(file_path).convert("RGB")
                    fo = BytesIO()
                    img.save(fo, format='bmp')
                    worksheet.insert_bitmap_data(
                        fo.getvalue(), line_count, count_header, x=0, y=0, scale_x=0.8, scale_y=0.14)
            count_header = 0
            count_header_end = 0
            line_count += 1
        fp = io.BytesIO()
        workbook.save(fp)
        data = base64.encodebytes(fp.getvalue())
        IrAttachment = self.env['ir.attachment']
        attachment_vals = {
            "name": self.name + '.xls',
            "res_model": "ir.ui.view",
            "type": "binary",
            "datas": data,
            "public": True,
        }
        fp.close()

        attachment = IrAttachment.search([('name', '=', self.name + '.xls'),
                                          ('type', '=', 'binary'),
                                          ('res_model', '=', 'ir.ui.view')],
                                         limit=1)
        if attachment:
            attachment.write(attachment_vals)
        else:
            attachment = IrAttachment.create(attachment_vals)
        # TODO: make user error here
        if not attachment:
            raise UserError('There is no attachments...')

        url = "/web/content/" + str(attachment.id) + "?download=true"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
