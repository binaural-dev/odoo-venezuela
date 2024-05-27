from datetime import datetime

import xlsxwriter
from odoo import _, api, models
from odoo.osv import expression

import logging

_logger = logging.getLogger(__name__)


class WizardAccountingReports(models.TransientModel):
    _inherit = "wizard.accounting.reports"

    def _determinate_resume_retention_books(self, moves):
        retention_resume_lines = []
        retention_moves = moves.filtered(lambda m: bool(m.retention_iva_line_ids.ids))
        credit_notes = retention_moves.filtered(
            lambda m: m.move_type in ["out_refund", "in_refund"]
        )
        retention_moves -= credit_notes

        retention_resume_lines.append(0.0)
        retention_resume_lines.append(
            sum(
                [
                    self._sum_retention_total(
                        move.retention_iva_line_ids.filtered(
                            lambda x: x.retention_id.state == "emitted"
                            and not self._check_future_retention_dates(
                                x.retention_id.date_accounting
                            )
                        )
                    )
                    for move in retention_moves
                ]
            )
        )
        retention_resume_lines.append(0.0)
        retention_resume_lines.append(
            sum(
                [
                    self._sum_retention_total(
                        move.retention_iva_line_ids.filtered(
                            lambda x: x.retention_id.state == "emitted"
                            and not self._check_future_retention_dates(
                                x.retention_id.date_accounting
                            )
                        )
                    )
                    * -1
                    for move in credit_notes
                ]
            )
        )

        return retention_resume_lines

    def _resume_sale_book_fields(self, moves):
        res_book = super()._resume_sale_book_fields(moves)
        res_book.extend(
            [
                {
                    "name": "Total Retenciones",
                    "format": "number",
                    "values": self._determinate_resume_retention_books(moves),
                }
            ]
        )

        return res_book

    def _resume_purchase_book_fields(self, moves):
        res_book = super()._resume_purchase_book_fields(moves)
        res_book.extend(
            [
                {
                    "name": "Total Retenciones",
                    "format": "number",
                    "values": self._determinate_resume_retention_books(moves),
                }
            ]
        )
        return res_book

    def sale_book_fields(self):
        fields = super().sale_book_fields()
        fields.extend(
            [
                {
                    "name": "Fecha Retención",
                    "field": "date_retention",
                    "size": 20,
                },
                {
                    "name": "N° Retención",
                    "field": "number_retention",
                    "size": 20,
                },
                {"name": "IVA retenido", "field": "iva_retained", "format": "number"},
            ]
        )
        return fields

    def purchase_book_fields(self):
        fields = super().purchase_book_fields()
        fields.extend(
            [
                {
                    "name": "Fecha Retención",
                    "field": "date_retention",
                    "size": 20,
                },
                {
                    "name": "N° Retención",
                    "field": "number_retention",
                    "size": 20,
                },
                {"name": "IVA retenido", "field": "iva_retained", "format": "number"},
            ]
        )
        return fields

    def _get_retention_domain(self):
        is_purchase = self.report == "purchase"
        field_date = "date" if is_purchase else "date_accounting"
        move_type = (
            ["out_invoice", "out_refund"] if not is_purchase else ["in_invoice", "in_refund"]
        )

        domain = [
            (field_date, ">=", self.date_from),
            (field_date, "<=", self.date_to),
            ("type", "in", move_type),
            ("type_retention", "=", "iva"),
            ("state", "=", "emitted"),
            ("company_id", "=", self.company_id.id),
        ]
        return domain

    def search_moves(self):
        retention = self.env["account.retention"]
        res_moves = super().search_moves()

        domain = self._get_retention_domain()
        retention_ids = retention.search(domain)
        moves = retention_ids.mapped("retention_line_ids.move_id")
        res_moves |= moves

        return res_moves

    def parse_sale_book_data(self):
        data = super().parse_sale_book_data()
        for move in data:
            date = move.get("accounting_date", False)
            if move.get("vat", "") != "RESUMEN" and (
                not date
                or self._check_future_retention_dates(
                    datetime.strptime(move.get("accounting_date"), "%d/%m/%Y").date()
                )
            ):
                move.update(
                    {
                        "total_sales_iva": 0,
                        "total_sales_not_iva": 0,
                        "amount_reduced_aliquot": 0,
                        "amount_general_aliquot": 0,
                        "tax_base_reduced_aliquot": 0,
                        "tax_base_general_aliquot": 0,
                    }
                )
            retention_data = self.get_retention_iva_values(move.get("_id"))
            move.update(retention_data)

        return data

    def parse_purchase_book_data(self):
        data = super().parse_purchase_book_data()
        for move in data:
            move_date = datetime.strptime(move.get("accounting_date"), "%d/%m/%Y").date()
            if self._check_future_retention_dates(move_date):
                move.update(
                    {
                        "total_purchases_iva": 0,
                        "total_purchases_not_iva": 0,
                        "amount_reduced_aliquot": 0,
                        "amount_general_aliquot": 0,
                        "amount_extend_aliquot": 0,
                        "tax_base_reduced_aliquot": 0,
                        "tax_base_general_aliquot": 0,
                        "tax_base_extend_aliquot": 0,
                    }
                )
            retention_data = self.get_retention_iva_values(move.get("_id"))
            move.update(retention_data)

        return data

    def get_retention_iva_values(self, move_id):
        move = self.env["account.move"].browse(move_id)
        is_purchase = self.report == "purchase"
        multiplier = -1 if move.move_type in ["out_refund", "in_refund"] else 1
        ret_lines = (
            move.retention_iva_line_ids.filtered(lambda x: x.retention_id.state == "emitted")
            if move.state == "posted"
            else move.retention_iva_line_ids
        )
        retention = ret_lines.mapped("retention_id")
        ret_vals = {
                    "date_retention": "",
                    "number_retention": "",
                    "iva_retained": 0,
                }

        if not ret_lines:
            return ret_vals
        
        for ret_line in ret_lines:

            if ret_line and self._check_future_retention_dates(ret_line.retention_id.date_accounting):
                continue

            ret_vals["date_retention"] = self._format_date(ret_line.mapped("retention_id").date)
            ret_vals["number_retention"] = move.iva_voucher_number
            ret_vals["iva_retained"] = ret_vals["iva_retained"] + (
                self._sum_retention_total(ret_line) * multiplier
                if ret_line.move_id.state != "cancel"
                else 0
            )

        return ret_vals

    def _sum_retention_total(self, lines):
        is_check_currency_system = self.currency_system
        retention = lines.mapped("retention_id")

        if (
            self.report == "purchase"
            and retention
            and self._check_future_retention_dates(retention.date)
            or lines.move_id.state == "cancel"
        ):
            return 0.0
        if not is_check_currency_system:
            return sum(lines.mapped("foreign_retention_amount"))

        return sum(lines.mapped("retention_amount"))

    def _check_future_retention_dates(self, cmp_date):
        return cmp_date < self.date_from or cmp_date > self.date_to
