from dateutil.relativedelta import relativedelta
from datetime import datetime
from io import BytesIO
from odoo import models, fields
import xlsxwriter
import logging

_logger = logging.getLogger(__name__)


class WizardAccountingReportsBinauralInvoice(models.TransientModel):
    _inherit = "wizard.accounting.reports"

    with_fiscal_machine = fields.Boolean(default=False)

    def _get_domain(self):
        res = super()._get_domain()
        if not self.with_fiscal_machine:
            return res
        res.append(("mf_invoice_number", "!=", False))
        res.append(("mf_reportz", "!=", False))
        return res

    def search_moves(self):
        if not self.with_fiscal_machine:
            return super().search_moves()

        move_model = self.env["account.move"]
        domain = self._get_domain()
        return move_model.search(domain, order="mf_invoice_number asc")

    def sale_book_fields(self):
        res = super().sale_book_fields()
        if not self.with_fiscal_machine:
            return res
        res.insert(5, {"name": "Reporte Z", "field": "mf_reportz"})
        return res

    def _fields_sale_book_line(self, move, taxes):
        res = super()._fields_sale_book_line(move, taxes)
        if not self.with_fiscal_machine:
            return res
        res["document_number"] = move.mf_invoice_number
        res["mf_reportz"] = move.mf_reportz
        return res

    def update_amounts(self, cumulative, amounts):
        return {
            "amount_untaxed": cumulative["amount_untaxed"] + amounts.get("amount_untaxed", 0),
            "amount_taxed": cumulative["amount_taxed"] + amounts.get("amount_taxed", 0),
            "tax_base_reduced_aliquot": cumulative["tax_base_reduced_aliquot"]
            + amounts.get("amount_taxed", 0),
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
            "move_type": self._determinate_type(data.get("move_type")),
            "transaction_type": "01-REG",
            "number_invoice_affected": "",
            "correlative": "",
            "reduced_aliquot": 0.08,
            "general_aliquot": 0.16,
            "total_sales_iva": amounts.get("amount_taxed") or 0,
            "total_sales_not_iva": amounts.get("amount_untaxed") or 0,
            "amount_reduced_aliquot": amounts.get("amount_reduced_aliquot") or 0,
            "amount_general_aliquot": amounts.get("amount_general_aliquot") or 0,
            "tax_base_reduced_aliquot": amounts.get("tax_base_reduced_aliquot") or 0,
            "tax_base_general_aliquot": amounts.get("tax_base_general_aliquot") or 0,
        }

    def parse_sale_book_data(self):
        if not self.with_fiscal_machine:
            return super().parse_sale_book_data()

        sale_book_lines = []
        moves = self.search_moves()
        _logger.info(moves)

        agrouped_by_report_z = {}

        init_cumulative = {
            "amount_untaxed": 0,
            "amount_taxed": 0,
            "tax_base_reduced_aliquot": 0,
            "amount_reduced_aliquot": 0,
            "tax_base_general_aliquot": 0,
            "amount_general_aliquot": 0,
        }
        cumulative = init_cumulative.copy()

        for move in moves:
            if not agrouped_by_report_z.get(move.mf_reportz):
                agrouped_by_report_z[move.mf_reportz] = move
            else:
                agrouped_by_report_z[move.mf_reportz] |= move

        for report in agrouped_by_report_z.items():
            range_start = 0
            data = {}
            cumulative = init_cumulative.copy()
            for index, move in enumerate(report[1]):
                next_move = move
                is_last_move = False
                if (index + 1) < len(report[1]):
                    next_move = report[1][index + 1]
                else:
                    is_last_move = True

                _logger.info("--------------------------")
                _logger.info("MOVE: %s", move.name)
                _logger.info("CUMULATIVE: %s", cumulative)
                amounts = self._determinate_amount_taxeds(move)
                cumulative = self.update_amounts(cumulative, amounts)


                if range_start == 0:
                    range_start = move.mf_invoice_number

                if move.move_type == "out_invoice":
                    if (
                        (
                            (
                                self._format_date(move.invoice_date)
                                != self._format_date(next_move.invoice_date)
                            )
                            or next_move.partner_id.prefix_vat == "J"
                            or next_move.partner_id.taxpayer_type == "special"
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
                        }

                        sale_book_lines.append(self._fields_sale_book_group_line(data, cumulative))
                        cumulative = init_cumulative.copy()
                        range_start = 0
                        continue
                    if not is_last_move and move.partner_id.taxpayer_type == "ordinary":
                        continue
                    sale_book_lines.append(self._fields_sale_book_line(move, amounts))
                    cumulative = init_cumulative.copy()
                    range_start = 0
        return sale_book_lines
