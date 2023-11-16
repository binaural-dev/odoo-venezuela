from odoo import fields, models, _
from odoo.tools import pycompat
from io import BytesIO
from datetime import datetime
from dateutil.relativedelta import relativedelta
import contextlib
import base64
import xlsxwriter

import logging

_logger = logging.getLogger(__name__)


class ProductTemplate(models.TransientModel):
    _name = "plu.product"

    company_id = fields.Many2one("res.company", default=lambda self: self.env.user.company_id)
    scale_model = fields.Selection(
        [("generic", "Generica"), ("cas5200", "CL 5200")], default="cas5200"
    )

    def download_plu_file(self):
        url_types = {
            "generic": "/web/binary/download_products_plu_csv?company_id=%s",
            "cas5200": "/web/binary/download_products_plu_cas_5200?company_id=%s",
        }

        return {
            "type": "ir.actions.act_url",
            "url": url_types[self.scale_model] % (self.env.company.id),
            "target": "self",
        }

    def get_udm(self):
        return [
            self.env.ref("uom.product_uom_gram").id,
            self.env.ref("uom.product_uom_kgm").id,
            self.env.ref("uom.product_uom_oz").id,
            self.env.ref("uom.product_uom_lb").id,
        ]

    def get_udm_extend(self):
        udm = self.get_udm()
        udm.append(self.env.ref("uom.product_uom_oz").id)
        udm.append(self.env.ref("uom.product_uom_lb").id)
        return udm

    def generate_plu_file_cas5200(self):
        file = BytesIO()

        workbook = xlsxwriter.Workbook(file, {"in_memory": True, "nan_inf_to_errors": True})
        worksheet = workbook.add_worksheet()

        headers = [
            "Departamento no",
            "PLU No",
            "Tipo de PLU",
            "Código del objeto",
            "Nombre1",
            "Category No",
            "Nombre3",
            "Grupo no",
            "Etiqueta no",
            "Etiqueta Aux No",
            "Origen no",
            "Nombre2",
            "Unidad de peso",
            "Peso fijo",
            "Imagen",
            "Precio unitario",
            "Piezas",
            "Sin impuesto",
            "Fecha de caducidad",
            "Vender por tiempo",
            "Ingrediente no",
            "Cantidad Unidad No",
            "Valor de tara",
            "Fecha de empaque",
            "Precio especial",
            "Código de barras no",
            "Departamento de enlace PLU1",
            "Usar tipo de precio fijo",
            "Fecha de actualización",
        ]

        for index, title in enumerate(headers):
            worksheet.write(0, index, title)

        udm = self.get_udm()

        products = self.env["product.template"].search(
            [
                ("plu_id", "!=", False),
                ("uom_id", "in", udm),
                ("company_id", "in", [self.company_id.id, False]),
            ]
        )

        def get_uom_id(product):
            uom = "0"
            if product.uom_id.id == self.env.ref("uom.product_uom_kgm").id:
                uom = "1"
            if product.uom_id.id == self.env.ref("uom.product_uom_gram").id:
                uom = "2"
            return uom

        txt = "{price:.2f}"
        for index_column, product in enumerate(products):
            p_index_column = index_column + 1
            worksheet.write(p_index_column, 0, "1")  # department
            worksheet.write(p_index_column, 1, product.plu_id)  # plu
            worksheet.write(p_index_column, 2, "1")  # type plu
            worksheet.write(p_index_column, 3, str(product.plu_id).zfill(5))  # Code obj
            worksheet.write(p_index_column, 4, str(product.name))  # name1
            worksheet.write(p_index_column, 5, "0")  # category
            worksheet.write(p_index_column, 6, "")  # name 3
            worksheet.write(p_index_column, 7, "0")  # group no
            worksheet.write(p_index_column, 8, "0")  # tag no
            worksheet.write(p_index_column, 9, "0")  # tag aux
            worksheet.write(p_index_column, 10, "0")  # Origen no
            worksheet.write(p_index_column, 11, "")  # name 2
            worksheet.write(p_index_column, 12, get_uom_id(product))  # udm
            worksheet.write(p_index_column, 13, "0")  # fixed weight
            worksheet.write(p_index_column, 14, "")  # image
            if product.list_price >= 0:
                worksheet.write(
                    p_index_column, 15, txt.format(price=product.list_price).replace(".", "")
                )  # price
            else:
                amount = txt.format(price=product.list_price)
                worksheet.write(p_index_column, 15, txt.format(price=amount.split(".")[1]))  # price
            worksheet.write(p_index_column, 16, "0")  # piece
            worksheet.write(p_index_column, 17, "0")  # taxes
            worksheet.write(p_index_column, 18, "0")  #  date end
            worksheet.write(p_index_column, 19, "0")  # sale date
            worksheet.write(p_index_column, 20, "0")  # ingredents
            worksheet.write(p_index_column, 21, "0")  # qty
            worksheet.write(p_index_column, 22, "0")  # tara
            worksheet.write(p_index_column, 23, "0")  # date
            worksheet.write(p_index_column, 24, "0")  # special price
            worksheet.write(p_index_column, 25, "12")  # barcode
            worksheet.write(p_index_column, 26, "0")  # barcode
            worksheet.write(p_index_column, 27, "0")  # use type

        workbook.close()
        return file.getvalue()

    def generate_plu_file(self):
        udm = self.get_udm_extend()
        for index, record in enumerate(self):
            products = record.env["product.template"].search(
                [
                    ("plu_id", "!=", False),
                    ("uom_id", "in", udm),
                    ("company_id", "=", [record.company_id.id, False]),
                ]
            )

            def get_uom_id(product):
                uom = "1"
                if product.uom_id.id == self.env.ref("uom.product_uom_kgm").id:
                    uom = "4"
                if product.uom_id.id == self.env.ref("uom.product_uom_oz").id:
                    uom = "5"
                if product.uom_id.id == self.env.ref("uom.product_uom_lb").id:
                    uom = "6"
                return uom

            with contextlib.closing(BytesIO()) as buf:
                writer = pycompat.csv_writer(buf, dialect="UNIX", delimiter=",")

                txt = "{price:.2f}"
                for index, x in enumerate(products):
                    writer.writerow(
                        [
                            index + 1,  # INDEX
                            x["name"][0:36],  # Name
                            str(x.plu_id),  # LFCode
                            "2" + str(x.plu_id).zfill(5),  # CODE
                            "27",  # Barcode
                            txt.format(price=x.list_price).replace(".", ""),  # UnitPrice
                            get_uom_id(x),  # WeightUnit
                            "1",  # Deptment
                            "0",  # WeightUnit
                            "30",  # Tare
                            "0",
                            "0",
                            "5",
                            str(index + 1),
                            "0",
                            "0",
                            "0",
                            "0",
                            "0",
                        ]
                    )
                out = buf.getvalue()
            return out
