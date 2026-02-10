from dateutil.relativedelta import relativedelta
from datetime import datetime
from io import BytesIO
from odoo import models, fields
from odoo.exceptions import UserError
import xlsxwriter
import logging
_logger = logging.getLogger(__name__)
class WizardAccountingReportsBinauralInvoice(models.TransientModel):
    _inherit = "wizard.accounting.reports"

    with_fiscal_machine = fields.Boolean(default=False)

    all_documents = fields.Boolean(
        default=False,
        string="Include all issued documents",
        help="It includes all documents, both those issued by a fiscal machine and those issued by free form.",
    )

    def _get_domain_all_documents(self):
        """ Get specific search domains for both free-form and fiscal machine documents.

        This method generates two separate domains to allow retrieving documents 
        from both sources independently:
        1. domain_free_form: The standard domain for traditional invoices.
        2. domain_fiscal_machine: A filtered domain that ensures the inclusion of 
           fiscal machine specific data (Serial, Report Z, and Fiscal Number).

        :return: A tuple containing (domain_free_form, domain_fiscal_machine).
        :rtype: tuple(list, list)
        """
        domain_free_form = self._get_domain()
        domain_fiscal_machine = self._get_domain()
        domain_fiscal_machine = [d for d in domain_fiscal_machine if d != ('correlative', 'not in', ['/', False])]
        domain_fiscal_machine.append(("mf_invoice_number", "!=", False))
        domain_fiscal_machine.append(("mf_reportz", "!=", False))
        domain_fiscal_machine.append(("mf_serial", "!=", False))
        return domain_free_form , domain_fiscal_machine

    def _get_domain(self):
        res = super()._get_domain()
        if not self.with_fiscal_machine:
            return res
        res = [d for d in res if d != ('correlative', 'not in', ['/', False])]
        res.append(("mf_invoice_number", "!=", False))
        res.append(("mf_reportz", "!=", False))
        res.append(("mf_serial", "!=", False))
        return res

    def search_moves(self):
        if self.with_fiscal_machine:
            res = super().search_moves()
            res = res.filtered_domain([("mf_serial", "!=", False)])
            res = res.sorted(key=lambda r: r.invoice_date)
            return res
        if self.all_documents:
            domain_free_form , domain_fiscal_machine = self._get_domain_all_documents()
            account_moves_free_form = self.env["account.move"].search(domain_free_form, order="invoice_date asc")
            account_moves_fiscal_machine = self.env["account.move"].search(domain_fiscal_machine, order="invoice_date asc")
            moves = account_moves_free_form + account_moves_fiscal_machine
            return moves.sorted(key=lambda r: r.invoice_date or r.date)
        move_model = self.env["account.move"]
        domain = self._get_domain()
        moves = move_model.search(domain, order="invoice_date asc")
        return moves

    def _get_sale_book_field_groups(self):
        sale_groups = super()._get_sale_book_field_groups()

        if not self.with_fiscal_machine and not self.all_documents:
            return sale_groups

        new_fields = [
            {"name": "Reporte Z", "field": "mf_reportz", "size": 16},
            {"name": "Serial de Maquina", "field": "mf_serial", "size": 16},
        ]

        for group in sale_groups:
            if group.get('header') == 'DETALLE DEL DOCUMENTO':
                basic_fields = group['fields']

                insertion_index = -1
                for i, field_dict in enumerate(basic_fields):
                    if field_dict.get('field') == 'move_type':
                        insertion_index = i + 1  
                        break

                if insertion_index != -1:

                    basic_fields.insert(insertion_index, new_fields[1]) 

                    basic_fields.insert(insertion_index, new_fields[0]) 

                break 

        return sale_groups

    def _fields_sale_book_line(self, move, taxes):
        res = super()._fields_sale_book_line(move, taxes)
        if not self.with_fiscal_machine and not self.all_documents:
            return res

        if self.with_fiscal_machine:
            del res["correlative"]

        if move.mf_invoice_number:
            res["document_number"] = move.mf_invoice_number

        if move.reversed_entry_id.mf_invoice_number:
            res["number_invoice_affected"] = move.reversed_entry_id.mf_invoice_number

        res.update({
            "mf_reportz": move.mf_reportz or "-",
            "mf_serial": move.mf_serial or "-",
        })
        return res

    def update_amounts(self, cumulative, amounts):
        return {
            "amount_taxed": cumulative["amount_taxed"] + amounts.get("amount_taxed", 0),
            "tax_base_exempt_aliquot": cumulative["tax_base_exempt_aliquot"]
            + amounts.get("tax_base_exempt_aliquot", 0),
            "tax_base_reduced_aliquot": cumulative["tax_base_reduced_aliquot"]
            + amounts.get("tax_base_reduced_aliquot", 0),
            "amount_reduced_aliquot": cumulative["amount_reduced_aliquot"]
            + amounts.get("amount_reduced_aliquot", 0),
            "tax_base_general_aliquot": cumulative["tax_base_general_aliquot"]
            + amounts.get("tax_base_general_aliquot", 0),
            "amount_general_aliquot": cumulative["amount_general_aliquot"]
            + amounts.get("amount_general_aliquot", 0),
        }

    def _fields_sale_book_group_line(self, data, amounts):
        return {
            "document_date": self._format_date(data.get("date")),
            "vat": "RESUMEN",
            "partner_name": "Resumen Diario de Ventas",
            "document_number": f"Desde {data.get('range_start')} Hasta {data.get('range_end')}",
            "mf_reportz": data.get("mf_reportz"),
            "mf_serial": data.get("mf_serial"),
            "move_type": self._determinate_type(data.get("move_type")),
            "transaction_type": "01-REG",
            "number_invoice_affected": "",
            "correlative": "",
            "reduced_aliquot": 0.08,
            "general_aliquot": 0.16,
            "total_sales_iva": amounts.get("amount_taxed", 0) - amounts.get("tax_base_exempt_aliquot", 0),
            "total_sales": amounts.get("amount_taxed", 0),
            "total_sales_not_iva": amounts.get("tax_base_exempt_aliquot", 0),
            "amount_reduced_aliquot": amounts.get("amount_reduced_aliquot", 0),
            "amount_general_aliquot": amounts.get("amount_general_aliquot", 0),
            "tax_base_reduced_aliquot": amounts.get("tax_base_reduced_aliquot", 0),
            "tax_base_general_aliquot": amounts.get("tax_base_general_aliquot", 0),
        }

    def parse_sale_book_data(self):
        if not self.with_fiscal_machine or self.all_documents:
            return super().parse_sale_book_data()

        sale_book_lines = []
        moves = self.search_moves()

        init_cumulative = {
            "tax_base_exempt_aliquot": 0,
            "amount_taxed": 0,
            "tax_base_reduced_aliquot": 0,
            "amount_reduced_aliquot": 0,
            "tax_base_general_aliquot": 0,
            "amount_general_aliquot": 0,
        }
        cumulative = init_cumulative.copy()

        agrouped_by_date = {}
        for move in moves:
            key = str(move.create_date.strftime("%d-%m-%Y"))
            if not agrouped_by_date.get(key):
                agrouped_by_date[key] = move
            else:
                agrouped_by_date[key] |= move

        for date_moves in agrouped_by_date.items():
            agrouped_by_report_z = {}
            for move in date_moves[1].sorted(lambda m: int(m.mf_invoice_number)):
                key = str(move.mf_serial) + "_" + str(move.mf_reportz)
                if not agrouped_by_report_z.get(key):
                    agrouped_by_report_z[key] = move
                else:
                    agrouped_by_report_z[key] |= move

            for report in agrouped_by_report_z.items():
                range_start = 0
                range_last = 0
                data = {}
                cumulative = init_cumulative.copy()
                for index, move in enumerate(report[1]):
                    next_move = move
                    is_last_move = False
                    if (index + 1) < len(report[1]):
                        next_move = report[1][index + 1]
                    else:
                        is_last_move = True

                    amounts = self._determinate_amount_taxeds(move)
                    cumulative = self.update_amounts(cumulative, amounts)

                    if range_start == 0:
                        range_start = move.mf_invoice_number

                    if move.move_type in ["out_invoice", "out_refund"]:
                        if move.move_type == "out_invoice" and move.journal_id.is_debit:
                            sale_book_lines.append(
                                self._fields_sale_book_line(move, amounts)
                            )
                            cumulative = init_cumulative.copy()
                            range_start = 0
                            continue
                        if (
                            move.partner_id.prefix_vat == "J"
                            or move.partner_id.taxpayer_type != "ordinary"
                            or move.move_type != "out_invoice"
                        ):
                            if cumulative["amount_taxed"] != amounts["amount_taxed"]:
                                data = {
                                    "move_type": move.move_type,
                                    "range_start": range_start,
                                    "range_end": (
                                        range_last
                                        if range_last != 0
                                        else move.mf_invoice_number
                                    ),
                                    "date": move.invoice_date,
                                    "mf_reportz": move.mf_reportz,
                                    "mf_serial": move.mf_serial,
                                }
                                range_last = 0
                                sale_book_lines.append(
                                    self._fields_sale_book_group_line(
                                        data, cumulative)
                                )
                            sale_book_lines.append(
                                self._fields_sale_book_line(move, amounts)
                            )
                            cumulative = init_cumulative.copy()
                            range_start = 0
                            continue

                        if (
                            (
                                (
                                    self._format_date(move.invoice_date)
                                    != self._format_date(next_move.invoice_date)
                                )
                                or next_move.partner_id.prefix_vat == "J"
                                or next_move.partner_id.taxpayer_type != "ordinary"
                                or next_move.move_type != "out_invoice"
                            )
                            or is_last_move
                        ) and move.partner_id.taxpayer_type == "ordinary":
                            data = {
                                "move_type": move.move_type,
                                "range_start": range_start,
                                "range_end": move.mf_invoice_number,
                                "date": move.invoice_date,
                                "mf_reportz": move.mf_reportz,
                                "mf_serial": move.mf_serial,
                            }
                            sale_book_lines.append(
                                self._fields_sale_book_group_line(
                                    data, cumulative)
                            )
                            cumulative = init_cumulative.copy()
                            range_start = 0
                            continue

                        if (
                            not is_last_move
                            and move.partner_id.taxpayer_type == "ordinary"
                        ):
                            range_last = move.mf_invoice_number
                            continue
                        range_last = move.mf_invoice_number
        return sale_book_lines
