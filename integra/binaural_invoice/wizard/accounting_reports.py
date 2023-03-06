from dateutil.relativedelta import relativedelta
from collections import OrderedDict
from datetime import datetime
from io import BytesIO

from odoo.exceptions import ValidationError
from odoo import models, fields, api, _

import pandas as pd
import xlsxwriter
import logging
import os


_logger = logging.getLogger(__name__)


class WizardAccountingReportsBinauralInvoice(models.TransientModel):
    _name = "wizard.accounting.reports"
    _description = "Wizard para generar reportes contables"

    report = fields.Selection(
        [("purchase", "Book Purchase"), ("sale", "Sale Book")],
        string="Report",
        required=True,
    )

    date_start = fields.Date(string="Date Start", required=True, default=fields.Date.today)

    date_end = fields.Date(
        string="Date End",
        required=True,
        default=fields.Date.today() + relativedelta(months=1, days=-1),
    )

    file = fields.Binary(string="File", readonly=True)

    file_name = fields.Char(string="File Name")

    company_id = fields.Many2one("res.company", default=lambda self: self.env.user.company_id.id)

    type_report = fields.Selection(
        [
            ("pdf", "PDF"),
            ("excel", "EXCEL"),
        ],
        "Format",
        required=True,
        default="excel",
    )

    currency_system = fields.Boolean(string="Report in currency system", default=False)

    def download_format():
        is_pdf = self.type_report == "pdf"

        if is_pdf:
            return ".pdf"

        return ".xlsx"

    def determinate_columns_report(type_report):
        return OrderedDict(
            [
                (_("Operation Number"), 0),
                (_("Date"), ""),
                (_("VAT"), ""),
                (_("Name/Bussiness Name"), ""),
                (_("Type"), ""),
                (_("Document Number"), ""),
                (_("Number Control"), ""),
                (_("Transaction Type"), ""),
                (_("Affected Document Number"), ""),
                (_("Total %ss Include IVA" % (type_report)), 0.00),
                (_("Total %ss Exempt" % (type_report)), 0.00),
                (_("Taxable16"), 0.00),
                (_("%16"), 0.00),
                (_("Tax16"), 0.00),
                (_("Taxable8"), 0.00),
                (_("%8"), 0.00),
                (_("Tax8"), 0.00),
                (_("Taxable31"), 0.00),
                (_("%31"), 0.00),
                (_("Tax31"), 0.00),
                (_("Retentions"), 0.00),
                (_("Retention Receipt"), ""),
                (_("Date Receipt"), ""),
            ]
        )

    def det_columns_resume(self):
        return OrderedDict(
            [
                ("_1", 0),
                ("_2", ""),
                ("_3", 0),
                ("_4", 0),
                ("_5", 0),
                ("_6", 0),
                ("_7", 0),
                ("_8", 0),
            ]
        )

    def generate_report(self):
        current_company = self.env.company
        is_purchase = self.report == "purchase"

        if is_purchase:
            moves_without_date = self.env["account.move"].search(
                [
                    ("state", "=", "cancel"),
                    ("invoice_date", "=", False),
                    ("company_id", "=", current_company.id),
                ]
            )

            if moves_without_date:
                raise ValidationError(
                    _(
                        "You have canceled supplier invoices registered in the system without the date of the invoice. Please correct to be able to download the book."
                    )
                )

        type_report = self.type_report
        is_pdf = type_report == "pdf"

        if is_pdf:
            return self.print_pdf()

        return self.print_xslx(current_company)

    def _get_domain(self, current_company_id=False):
        search_domain = []
        is_purchase = self.report == "purchase"

        field_date = "invoice_date" if is_purchase else "date"

        if current_company_id:
            search_domain += [("company_id", "=", current_company_id)]

        move_type = (
            ["out_invoice", "out_refund"]
            if not is_purchase
            else ["in_invoice", "in_refund", "in_debit"]
        )

        search_domain += [(field_date, ">=", self.date_start)]
        search_domain += [(field_date, "<=", self.date_end)]
        search_domain += [
            ("state", "not in", ["draft"]),
            ("journal_id.fiscal", "=", True),
            ("move_type", "in", move_type),
        ]

        return search_domain

    def print_pdf(self):
        raise ValidationError(_("Cannot download as PDF, try Excel."))

    def print_xslx(self, current_company):
        report = self.report
        is_purchase = report == "purchase"
        filecontent = ""
        wizard_id = str(self.id)
        current_company_id = str(current_company.id)

        name = "%ss Book" % (report.capitalize())
        date_start = str(self.date_start)
        date_end = str(self.date_end)

        if is_purchase:
            table = self._table_purchase_book(self.id, current_company)
            table_resume = self._table_resume_shopping_book(self.id, current_company)
        else:
            table = self._table_sale_book(self.id, current_company)
            table_resume = self._table_resume_sale_book(self.id, current_company)

        if not table.empty and name:
            filecontent = (
                self._excel_file_purchase(
                    table, name, date_start, date_end, table_resume, current_company
                )
                if is_purchase
                else self._excel_file_sale(
                    table, name, date_start, date_end, table_resume, current_company
                )
            )

        return {
            "type": "ir.actions.act_url",
            "url": "/web/get_excel?report=%s&wizard=%s&date_start=%s&date_end=%s&current_company_id=%s"
            % (report, wizard_id, date_start, date_end, current_company_id),
            "target": "self",
        }

    def _table_sale_book(self, wizard=False, current_company=False):
        wiz = self

        if not wizard:
            wiz = self.search([("id", "=", wizard)])

        table = wiz._sale_book_invoice(current_company)

        return pd.concat([table])

    def _sale_book_invoice(self, current_company=False):

        company_id = current_company.id if current_company else current_company
        type_report = self.report.capitalize()
        
        search_domain = self._get_domain(company_id)    
        invoices = self.env["account.move"].search(search_domain, order="id asc")
        invoices_id = invoices.ids
        
        columns = self.determinate_columns_report()

        lista = []
        op = 1
        for invoice in invoices:
            columns.update(columns)
            base = 0.00
            base16 = 0.00
            base8 = 0.00
            imp16 = 0.00
            imp8 = 0.00
            not_gravable = 0.00
            if self.currency_system:
                for line in invoice.total_taxed:
                    
                    tax_id = self.env["account.tax"].search(
                        [("tax_purchase_id", "=", line[6]), ("type_tax_use", "=", "sale")], limit=1
                    )
                    if tax_id.amount > 0:
                        if tax_id.amount == 16:
                            base16 = line[2]
                            imp16 = line[1]
                        if tax_id.amount == 8:
                            base8 = line[2]
                            imp8 = line[1]
                        base += line[2]
                    else:
                        not_gravable += line[2]
            else:
                for line in invoice.foreign_tax_totals:
                    for key in line:
                        _logger.warning('line %s' % key)
                    tax_id = self.env["account.tax"].search(
                        [("tax_group_id", "=", line[6]), ("type_tax_use", "=", "sale")], limit=1
                    )
                    if tax_id.amount > 0:
                        if tax_id.amount == 16:
                            base16 = line[2]
                            imp16 = line[1]
                        if tax_id.amount == 8:
                            base8 = line[2]
                            imp8 = line[1]
                        base += line[2]
                    else:
                        not_gravable += line[2]
            dict["Nª de Ope"] = 0
            f = i.invoice_date
            fn = datetime.strptime(str(f), "%Y-%m-%d")
            dict["Fecha"] = fn.strftime("%d/%m/%Y")
            dict["R.I.F"] = i.partner_id.prefix_vat + i.partner_id.vat
            dict["Nombre/Razón Social"] = i.partner_id.name
            if i.move_type_alternative in ["out_debit"]:
                dict["Tipo"] = "ND"
            elif i.move_type in ["out_invoice"]:
                dict["Tipo"] = "FAC"
            elif i.move_type == "out_refund":
                dict["Tipo"] = "NC"
            else:
                dict["Tipo"] = i.move_type

            dict["Nª de Doc"] = i.name
            dict["Nª de Control"] = i.correlative

            dict["Nª de Doc. Afectado"] = i.reversed_entry_id.name if i.reversed_entry_id else ""

            if i.move_type in ["out_invoice"] and i.state in ["posted"]:
                dict["Tipo Transacción"] = "01-REG"
            if i.move_type in ["out_invoice"] and i.state in ["cancel"]:
                dict["Tipo Transacción"] = "03-ANU"
            if i.move_type_alternative in ["out_debit"] and i.state in ["posted"]:
                dict["Tipo Transacción"] = "02-REG"
                dict["Nª de Doc. Afectado"] = i.debit_origin_id.name if i.debit_origin_id else ""
            if i.move_type in ["out_refund"] and i.state in ["posted"]:
                dict["Tipo Transacción"] = "03-REG"
            if i.move_type in ["out_refund", "out_debit"] and i.state in ["cancel"]:
                dict["Tipo Transacción"] = "03-ANU"

            if i.state in ["posted"]:
                if self.currency_sistem:
                    dict["Total Ventas incluye IVA"] = (
                        i.amount_total
                        if i.move_type in ["out_invoice", "out_debit"]
                        else -i.amount_total
                    )
                    dict["Total Ventas Exentas"] = (
                        not_gravable
                        if i.move_type in ["out_invoice", "out_debit"]
                        else -not_gravable
                    )
                    dict["Imponible16"] = (
                        base16 if i.move_type in ["out_invoice", "out_debit"] else -base16
                    )
                    dict["%16"] = 0.16
                    dict["Impuesto16"] = (
                        imp16 if i.move_type in ["out_invoice", "out_debit"] else -imp16
                    )
                    dict["Imponible8"] = (
                        base8 if i.move_type in ["out_invoice", "out_debit"] else -base8
                    )
                    dict["%8"] = 0.08
                    dict["Impuesto8"] = (
                        imp8 if i.move_type in ["out_invoice", "out_debit"] else -imp8
                    )
                    dict["Retenciones"] = (
                        amount_retention
                        if i.move_type in ["out_invoice", "out_debit"]
                        else -amount_retention
                    )
                else:
                    dict["Total Ventas incluye IVA"] = (
                        i.foreign_amount_total
                        if i.move_type in ["out_invoice", "out_debit"]
                        else -i.foreign_amount_total
                    )
                    dict["Total Ventas Exentas"] = (
                        not_gravable
                        if i.move_type in ["out_invoice", "out_debit"]
                        else -not_gravable
                    )
                    dict["Imponible16"] = (
                        base16 if i.move_type in ["out_invoice", "out_debit"] else -base16
                    )
                    dict["%16"] = 0.16
                    dict["Impuesto16"] = (
                        imp16 if i.move_type in ["out_invoice", "out_debit"] else -imp16
                    )
                    dict["Imponible8"] = (
                        base8 if i.move_type in ["out_invoice", "out_debit"] else -base8
                    )
                    dict["%8"] = 0.08
                    dict["Impuesto8"] = (
                        imp8 if i.move_type in ["out_invoice", "out_debit"] else -imp8
                    )
                    dict["Retenciones"] = (
                        amount_retention
                        if i.move_type in ["out_invoice", "out_debit"]
                        else -amount_retention
                    )

                dict["Comprobante de Ret."] = retention_number
                if retention_date:
                    fr = retention_date
                    fnr = datetime.strptime(str(fr), "%Y-%m-%d")
                    dict["Fecha de Comprobante"] = fnr.strftime("%d/%m/%Y")
                else:
                    dict["Fecha de Comprobante"] = ""
            else:
                dict["Total Ventas incluye IVA"] = 0.00
                dict["Total Ventas Exentas"] = 0.00
                dict["Imponible16"] = 0.00
                dict["%16"] = 0.16
                dict["Impuesto16"] = 0.00
                dict["Imponible8"] = 0.00
                dict["%8"] = 0.08
                dict["Impuesto8"] = 0.00
                dict["Retenciones"] = 0.00
                dict["Comprobante de Ret."] = ""
                dict["Fecha de Comprobante"] = ""
            lista.append(dict)  
        
        lista.sort(key=lambda date: datetime.strptime(date["Fecha"], "%d/%m/%Y"))
        for item in lista:
            item["Nª de Ope"] = op
            op += 1
        tabla = pd.DataFrame(lista)
        return tabla
    
    def _table_resume_sale_book(self, wizard=False, current_company = False):
        if wizard:
            wiz = self.search([("id", "=", wizard)])
        else:
            wiz = self
        tabla1 = wiz._sale_book_invoice_resume_excel(current_company)
        
        return pd.concat([tabla1])
    
    def _sale_book_invoice_resume_excel(self, current_company = False):
        dic = self.det_columns_resume()
        tabla = self._sale_book_invoice(current_company)
        if len(tabla.columns) > 0:
            tabla.columns = tabla.columns.map(lambda x: x.replace(" ", "_"))
            is_fact = tabla["Tipo"] == "FAC"
            is_nd = tabla["Tipo"] == "ND"
            is_nc = tabla["Tipo"] == "NC"
            _logger.info(is_nd)
            tabla_fan = tabla[is_fact]
            tabla_nd = tabla[is_nd]
            tabla_nc = tabla[is_nc]
            sum_tabla_fan = tabla_fan.sum(axis=0, skipna=True)
            sum_tabla_nd = tabla_nd.sum(axis=0, skipna=True)
            sum_tabla_nc = tabla_nc.sum(axis=0, skipna=True)
            _logger.info("nd")
            _logger.info("nd")
            _logger.info(sum_tabla_nd)
            lista = []
            dict = OrderedDict()
            dict.update(dic)
            dict["_1"] = 1
            dict["_2"] = "Ventas Internas No Gravadas"
            dict["_3"] = (
                sum_tabla_fan["Total_Ventas_Exentas"] + sum_tabla_nd["Total_Ventas_Exentas"]
            )
            dict["_4"] = 0.00
            dict["_5"] = sum_tabla_nc["Total_Ventas_Exentas"]
            dict["_6"] = 0.00
            dict["_7"] = (
                sum_tabla_fan["Total_Ventas_Exentas"]
                + sum_tabla_nd["Total_Ventas_Exentas"]
                + sum_tabla_nc["Total_Ventas_Exentas"]
            )
            dict["_8"] = 0.00
            lista.append(dict)
            dict = OrderedDict()
            dict.update(dic)
            dict["_1"] = 2
            dict["_2"] = "Exportaciones Gravadas por Alícuota General"
            dict["_3"] = 0.00
            dict["_4"] = 0.00
            dict["_5"] = 0.00
            dict["_6"] = 0.00
            dict["_7"] = 0.00
            dict["_8"] = 0.00
            lista.append(dict)
            dict = OrderedDict()
            dict.update(dic)
            dict["_1"] = 3
            dict["_2"] = "Exportaciones Gravadas por Alícuota General más Adicional"
            dict["_3"] = 0.00
            dict["_4"] = 0.00
            dict["_5"] = 0.00
            dict["_6"] = 0.00
            dict["_7"] = 0.00
            dict["_8"] = 0.00
            lista.append(dict)
            dict = OrderedDict()
            dict.update(dic)
            dict["_1"] = 4
            dict["_2"] = "Ventas Internas Gravadas sólo por Alícuota General"
            dict["_3"] = sum_tabla_fan["Imponible16"] + sum_tabla_nd["Imponible16"]
            dict["_4"] = sum_tabla_fan["Impuesto16"] + sum_tabla_nd["Impuesto16"]
            dict["_5"] = sum_tabla_nc["Imponible16"]
            dict["_6"] = sum_tabla_nc["Impuesto16"]
            dict["_7"] = (
                sum_tabla_fan["Imponible16"]
                + sum_tabla_nd["Imponible16"]
                + sum_tabla_nc["Imponible16"]
            )
            dict["_8"] = (
                sum_tabla_fan["Impuesto16"]
                + sum_tabla_nd["Impuesto16"]
                + sum_tabla_nc["Impuesto16"]
            )
            lista.append(dict)
            dict = OrderedDict()
            dict.update(dic)
            dict["_1"] = 5
            dict["_2"] = "Ventas Internas Gravadas por Alícuota General más Adicional"
            dict["_3"] = 0.00
            dict["_4"] = 0.00
            dict["_5"] = 0.00
            dict["_6"] = 0.00
            dict["_7"] = 0.00
            dict["_8"] = 0.00
            lista.append(dict)
            dict = OrderedDict()
            dict.update(dic)
            dict["_1"] = 6
            dict["_2"] = "Ventas Internas Gravadas por Alícuota Reducida"
            dict["_3"] = sum_tabla_fan["Imponible8"] + sum_tabla_nd["Imponible8"]
            dict["_4"] = sum_tabla_fan["Impuesto8"] + sum_tabla_nd["Impuesto8"]
            dict["_5"] = sum_tabla_nc["Imponible8"]
            dict["_6"] = sum_tabla_nc["Impuesto8"]
            dict["_7"] = (
                sum_tabla_fan["Imponible8"]
                + sum_tabla_nd["Imponible8"]
                + sum_tabla_nc["Imponible8"]
            )
            dict["_8"] = (
                sum_tabla_fan["Impuesto8"] + sum_tabla_nd["Impuesto8"] + sum_tabla_nc["Impuesto8"]
            )
            lista.append(dict)
            dict = OrderedDict()
            dict.update(dic)
            dict["_1"] = 7
            dict["_2"] = "Ajustes a los Débitos Fiscales de Periodos Anteriores"
            dict["_3"] = 0.00
            dict["_4"] = 0.00
            dict["_5"] = 0.00
            dict["_6"] = 0.00
            dict["_7"] = 0.00
            dict["_8"] = 0.00
            lista.append(dict)
            dict = OrderedDict()
            dict.update(dic)
            dict["_1"] = 8
            dict["_2"] = "Total Ventas y Débitos Fiscales del Periodo"
            dict["_3"] = (
                sum_tabla_fan["Total_Ventas_Exentas"]
                + sum_tabla_nd["Total_Ventas_Exentas"]
                + sum_tabla_fan["Imponible16"]
                + sum_tabla_nd["Imponible16"]
                + sum_tabla_fan["Imponible8"]
                + sum_tabla_nd["Imponible8"]
            )
            dict["_4"] = (
                sum_tabla_fan["Impuesto16"]
                + sum_tabla_nd["Impuesto16"]
                + sum_tabla_fan["Impuesto8"]
                + sum_tabla_nd["Impuesto8"]
            )
            dict["_5"] = (
                sum_tabla_nc["Total_Ventas_Exentas"]
                + sum_tabla_nc["Imponible16"]
                + sum_tabla_nc["Imponible8"]
            )
            dict["_6"] = sum_tabla_nc["Impuesto16"] + sum_tabla_nc["Impuesto8"]
            dict["_7"] = (
                sum_tabla_fan["Total_Ventas_Exentas"]
                + sum_tabla_nd["Total_Ventas_Exentas"]
                + sum_tabla_fan["Imponible16"]
                + sum_tabla_fan["Imponible8"]
                + sum_tabla_nd["Imponible16"]
                + sum_tabla_nd["Imponible8"]
                + sum_tabla_nc["Total_Ventas_Exentas"]
                + sum_tabla_nc["Imponible16"]
                + sum_tabla_nc["Imponible8"]
            )
            dict["_8"] = (
                sum_tabla_fan["Impuesto16"]
                + sum_tabla_nd["Impuesto16"]
                + sum_tabla_nc["Impuesto16"]
                + sum_tabla_fan["Impuesto8"]
                + sum_tabla_nd["Impuesto8"]
                + sum_tabla_nc["Impuesto8"]
            )
            lista.append(dict)
            dict = OrderedDict()
            dict.update(dic)
            dict["_1"] = 9
            dict["_2"] = "Total Retenciones"
            dict["_3"] = 0.00
            dict["_4"] = 0.00
            dict["_5"] = 0.00
            dict["_6"] = 0.00
            dict["_7"] = 0.00
            dict["_8"] = (
                sum_tabla_fan["Retenciones"]
                + sum_tabla_nd["Retenciones"]
                + sum_tabla_nc["Retenciones"]
            )
            lista.append(dict)
            tabla = pd.DataFrame(lista)
        return tabla
    
    def sum_sale_book_invoice(self):
        tabla = self._sale_book_invoice()
        tabla.columns = tabla.columns.map(lambda x: x.replace(" ", "_"))
        sum_tabla = tabla.sum(axis=0, skipna=True)
        return sum_tabla
    
    def _excel_file_sale(self, table, name, start, end, table_resumen, current_company):
        # company = self.env['res.company'].search([], limit=1)
        company = current_company
        data2 = BytesIO()
        workbook = xlsxwriter.Workbook(data2, {'in_memory': True,'nan_inf_to_errors': True})
        merge_format = workbook.add_format({
            'bold': 1,
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'fg_color': 'gray'})
        datos = table
        datos_resumen = table_resumen
        total_1 = 0.00
        total_2 = 0.00
        total_3 = 0.00
        total_4 = 0.00
        total_5 = 0.00
        total_6 = 0.00
        total_7 = 0.00
        range_start = 'Desde: ' + datetime.strptime(start, '%Y-%m-%d').strftime('%d/%m/%Y')
        range_end = 'Hasta: ' + datetime.strptime(end, '%Y-%m-%d').strftime('%d/%m/%Y')
        worksheet2 = workbook.add_worksheet(name)
        worksheet2.set_column('A:C', 20)
        worksheet2.set_column('D:D', 30)
        worksheet2.set_column('E:I', 20)
        worksheet2.set_column('J:J', 30)
        worksheet2.set_column('K:R', 20)
        worksheet2.set_column('S:T', 30)
        worksheet2.write('A1', company.name)
        worksheet2.write('A2', name)
        worksheet2.write('A3', company.vat)
        worksheet2.write('A4', range_start)
        worksheet2.write('A5', range_end)
        worksheet2.merge_range('L5:N5','VENTAS INTERNAS ALÍCUOTA GENERAL', merge_format)
        worksheet2.merge_range('O5:Q5','VENTAS INTERNAS ALÍCUOTA REDUCIDA', merge_format)
        worksheet2.write('A6', 'Nª de Ope')
        worksheet2.write('B6', 'Fecha')
        worksheet2.write('C6', 'R.I.F')
        worksheet2.write('D6', 'Nombre/Razón Social')
        worksheet2.write('E6', 'Tipo')
        worksheet2.write('F6', 'Nª de Doc')
        worksheet2.write('G6', 'Nª de Control')
        worksheet2.write('H6', 'Tipo Transacción')
        worksheet2.write('I6', 'Nª de Doc. Afectado')
        worksheet2.write('J6', 'Total Ventas incluye IVA')
        worksheet2.write('K6', 'Total Ventas Exentas')
        worksheet2.write('L6', 'Imponible')
        worksheet2.write('M6', '%')
        worksheet2.write('N6', 'Impuesto')
        worksheet2.write('O6', 'Imponible')
        worksheet2.write('P6', '%')
        worksheet2.write('Q6', 'Impuesto')
        worksheet2.write('R6', 'Retenciones')
        worksheet2.write('S6', 'Comprobante de Ret.')
        worksheet2.write('T6', 'Fecha de Comprobante')
        worksheet2.set_row(5, 20, merge_format)
        columnas = list(datos.columns.values)
        columnas_resumen = list(datos_resumen.columns.values)
        columns2 = [{'header': r} for r in columnas]
        columns2_resumen = [{'header': r} for r in columnas_resumen]
        columns2[0].update({'total_string': 'Total'})
        data = datos.values.tolist()
        data_resumen = datos_resumen.values.tolist()
        currency_format = workbook.add_format({'num_format': '#,###0.00'})
        porcent_format = workbook.add_format({'num_format': '#,###0.00" "%'})
        date_format = workbook.add_format()
        date_format.set_num_format('d-mmm-yy')  # Format string.
        col3 = len(columns2) - 1
        col2 = len(data) + 6
        for record in columns2[9:12]:
            record.update({'format': currency_format})
        for record in columns2[13:15]:
            record.update({'format': currency_format})
        for record in columns2[16:18]:
            record.update({'format': currency_format})
        for record in columns2[12:13]:
            record.update({'format': porcent_format})
        for record in columns2[15:16]:
            record.update({'format': porcent_format})
        for record in columns2[18:19]:
            record.update({'format': porcent_format})
        i = 0
        while i < len(data):
            total_1 += data[i][9]
            total_2 += data[i][10]
            total_3 += data[i][11]
            total_4 += data[i][13]
            total_5 += data[i][14]
            total_6 += data[i][16]
            total_7 += data[i][17]
            i += 1
        worksheet2.write_number(col2, 9, float(total_1), currency_format)
        worksheet2.write_number(col2, 10, float(total_2), currency_format)
        worksheet2.write_number(col2, 11, float(total_3), currency_format)
        worksheet2.write_number(col2, 13, float(total_4), currency_format)
        worksheet2.write_number(col2, 14, float(total_5), currency_format)
        worksheet2.write_number(col2, 16, float(total_6), currency_format)
        worksheet2.write_number(col2, 17, float(total_7), currency_format)
        cells = xlsxwriter.utility.xl_range(6, 0, col2, col3)
        worksheet2.add_table(cells, {'data': data, 'total_row': True, 'columns': columns2, 'header_row': False})
        encabezado = 4 + len(data) + 5
        detalle_enc = encabezado + 1
        col6 = detalle_enc
        col4 = len(columnas_resumen) - 1
        col5 = len(data) + 6 + 6 + len(data_resumen)
        for record in columns2_resumen[2:8]:
            record.update({'format': currency_format})
        cells_resumen = xlsxwriter.utility.xl_range(col6, 0, col5, col4)
        worksheet2.add_table(
            cells_resumen, {'data': data_resumen, 'total_row': True, 'columns': columns2_resumen, 'header_row': False})
        worksheet2.merge_range(str('A') + str(encabezado) + ':' + str('B') + str(encabezado), 'Resumen', merge_format)
        worksheet2.merge_range(str('C') + str(encabezado) + ':' + str('D') + str(encabezado),
                               'Facturas / Notas de Débito', merge_format)
        worksheet2.merge_range(str('E') + str(encabezado) + ':' + str('F') + str(encabezado), 'Notas de Crédito',
                               merge_format)
        worksheet2.merge_range(str('G') + str(encabezado) + ':' + str('H') + str(encabezado), 'Total Neto',
                               merge_format)

        worksheet2.write(str('A') + str(detalle_enc), '', merge_format)
        worksheet2.write(str('B') + str(detalle_enc), 'Débitos Fiscales',
                         merge_format)
        worksheet2.write(str('C') + str(detalle_enc), 'Base Imponible',
                         merge_format)
        worksheet2.write(str('D') + str(detalle_enc), 'Débito Fiscal', merge_format)
        worksheet2.write(str('E') + str(detalle_enc), 'Base Imponible', merge_format)
        worksheet2.write(str('F') + str(detalle_enc), 'Débito Fiscal',
                         merge_format)
        worksheet2.write(str('G') + str(detalle_enc), 'Base Imponible',
                         merge_format)
        worksheet2.write(str('H') + str(detalle_enc), 'Débito Fiscal', merge_format)
        
        workbook.close()
        data2 = data2.getvalue()
        return data2
