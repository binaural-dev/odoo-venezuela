from odoo import fields, models

# Filtro de numero de control que el libro general usa para EXCLUIR los
# documentos sin correlative (los emitidos por maquina fiscal). Se elimina del
# dominio cuando se piden los documentos fiscales.
CORRELATIVE_LEAF = ("correlative", "not in", ["/", False])


class WizardAccountingReports(models.TransientModel):
    """Extiende el Libro de Compras/Ventas para poder incluir los documentos
    emitidos por maquina fiscal, que no llevan numero de control (`correlative`)
    y por eso el libro general los descarta.

    Dos opciones (mutuamente excluyentes en la vista):
    - `with_fiscal_machine`: SOLO documentos de maquina fiscal, presentados como
      Resumen Diario de Ventas agrupado por Reporte Z.
    - `all_documents`: TODOS los documentos (forma libre + maquina fiscal),
      linea por linea.
    """

    _inherit = "wizard.accounting.reports"

    with_fiscal_machine = fields.Boolean(
        string="Con máquina fiscal",
        default=False,
        help="Muestra únicamente los documentos emitidos por máquina fiscal, "
        "agrupados como Resumen Diario de Ventas por Reporte Z.",
    )
    all_documents = fields.Boolean(
        string="Incluir todos los documentos emitidos",
        default=False,
        help="Incluye en el libro tanto los documentos con número de control "
        "(forma libre) como los emitidos por máquina fiscal.",
    )

    # ------------------------------------------------------------------
    # Dominios
    # ------------------------------------------------------------------
    def _fiscal_machine_domain(self, domain):
        """Devuelve `domain` sin el filtro de número de control y exigiendo los
        datos de máquina fiscal (serial, Reporte Z y número de máquina)."""
        domain = [leaf for leaf in domain if tuple(leaf) != CORRELATIVE_LEAF]
        domain += [
            ("mf_invoice_number", "!=", False),
            ("mf_reportz", "!=", False),
            ("mf_serial", "!=", False),
        ]
        return domain

    def _get_domain(self):
        domain = super()._get_domain()
        if not self.with_fiscal_machine:
            return domain
        return self._fiscal_machine_domain(domain)

    def _get_domain_all_documents(self):
        """Dos dominios independientes: forma libre (con número de control) y
        máquina fiscal (sin número de control, con datos de MF)."""
        domain_free_form = super()._get_domain()
        domain_fiscal_machine = self._fiscal_machine_domain(super()._get_domain())
        return domain_free_form, domain_fiscal_machine

    # ------------------------------------------------------------------
    # Búsqueda de asientos
    # ------------------------------------------------------------------
    def _mf_sort_number(self, move):
        number = move.mf_invoice_number or ""
        return int(number) if number.isdigit() else 0

    def search_moves(self):
        if self.all_documents:
            domain_free_form, domain_fiscal_machine = self._get_domain_all_documents()
            AccountMove = self.env["account.move"]
            moves = AccountMove.search(domain_free_form) | AccountMove.search(
                domain_fiscal_machine
            )
            return moves.sorted(key=lambda m: m.invoice_date_display or m.date)
        if self.with_fiscal_machine:
            moves = super().search_moves()
            return moves.sorted(
                key=lambda m: (m.invoice_date_display or m.date, self._mf_sort_number(m))
            )
        return super().search_moves()

    # ------------------------------------------------------------------
    # Columnas extra de máquina fiscal en el libro de ventas
    # ------------------------------------------------------------------
    def _get_sale_book_field_groups(self):
        groups = super()._get_sale_book_field_groups()
        if not (self.with_fiscal_machine or self.all_documents):
            return groups

        extra_fields = [
            {"name": "N° Máquina Fiscal", "field": "mf_invoice_number", "size": 16},
            {"name": "Reporte Z", "field": "mf_reportz", "size": 16},
            {"name": "Serial de Máquina", "field": "mf_serial", "size": 16},
        ]

        for group in groups:
            if group.get("header") == "DETALLE DEL DOCUMENTO":
                group_fields = group["fields"]
                insertion_index = next(
                    (
                        i + 1
                        for i, field_dict in enumerate(group_fields)
                        if field_dict.get("field") == "move_type"
                    ),
                    None,
                )
                if insertion_index is not None:
                    for offset, column in enumerate(extra_fields):
                        group_fields.insert(insertion_index + offset, column)
                break
        return groups

    def _fields_sale_book_line(self, move, taxes):
        res = super()._fields_sale_book_line(move, taxes)
        if not (self.with_fiscal_machine or self.all_documents):
            return res
        res["mf_invoice_number"] = move.mf_invoice_number or "-"
        res["mf_reportz"] = move.mf_reportz or "-"
        res["mf_serial"] = move.mf_serial or "-"
        if move.reversed_entry_id and move.reversed_entry_id.mf_invoice_number:
            res["number_invoice_affected"] = move.reversed_entry_id.mf_invoice_number
        return res

    # ------------------------------------------------------------------
    # Resumen Diario de Ventas (solo modo "Con máquina fiscal")
    # ------------------------------------------------------------------
    _MF_AMOUNT_KEYS = (
        "amount_taxed",
        "tax_base_exempt_aliquot",
        "tax_base_reduced_aliquot",
        "amount_reduced_aliquot",
        "tax_base_general_aliquot",
        "amount_general_aliquot",
        "tax_base_extend_aliquot",
        "amount_extend_aliquot",
    )

    def _mf_init_cumulative(self):
        return {key: 0 for key in self._MF_AMOUNT_KEYS}

    def update_amounts(self, cumulative, amounts):
        return {
            key: cumulative.get(key, 0) + amounts.get(key, 0)
            for key in self._MF_AMOUNT_KEYS
        }

    def _fields_sale_book_group_line(self, data, amounts):
        amount_taxed = amounts.get("amount_taxed", 0)
        exempt = amounts.get("tax_base_exempt_aliquot", 0)
        return {
            "document_date": self._format_date(data.get("date")),
            "accounting_date": self._format_date(data.get("date")),
            "vat": "RESUMEN",
            "partner_name": "Resumen Diario de Ventas",
            "move_type": self._determinate_type(data.get("move_type")),
            "invoice_number": f"Desde {data.get('range_start')} Hasta {data.get('range_end')}",
            "credit_note_number": "--",
            "debit_note_number": "--",
            "correlative": "--",
            "mf_invoice_number": f"{data.get('range_start')} - {data.get('range_end')}",
            "mf_reportz": data.get("mf_reportz"),
            "mf_serial": data.get("mf_serial"),
            "transaction_type": "01-REG",
            "number_invoice_affected": "",
            "reduced_aliquot": 0.08,
            "general_aliquot": 0.16,
            "extend_aliquot": 0.31,
            "total_sales": amount_taxed,
            "total_sales_iva": amount_taxed - exempt,
            "total_sales_not_iva": exempt,
            "amount_reduced_aliquot": amounts.get("amount_reduced_aliquot", 0),
            "amount_general_aliquot": amounts.get("amount_general_aliquot", 0),
            "amount_extend_aliquot": amounts.get("amount_extend_aliquot", 0),
            "tax_base_reduced_aliquot": amounts.get("tax_base_reduced_aliquot", 0),
            "tax_base_general_aliquot": amounts.get("tax_base_general_aliquot", 0),
            "tax_base_extend_aliquot": amounts.get("tax_base_extend_aliquot", 0),
        }

    def parse_sale_book_data(self):
        # all_documents y forma libre: linea por linea (comportamiento base, con
        # las columnas de MF que añade _fields_sale_book_line).
        if self.all_documents or not self.with_fiscal_machine:
            return super().parse_sale_book_data()

        sale_book_lines = []
        moves = self.search_moves()

        agrouped_by_date = {}
        for move in moves:
            key = move.create_date.strftime("%d-%m-%Y")
            if not agrouped_by_date.get(key):
                agrouped_by_date[key] = move
            else:
                agrouped_by_date[key] |= move

        for _date_key, date_moves in agrouped_by_date.items():
            agrouped_by_report_z = {}
            for move in date_moves.sorted(self._mf_sort_number):
                key = f"{move.mf_serial}_{move.mf_reportz}"
                if not agrouped_by_report_z.get(key):
                    agrouped_by_report_z[key] = move
                else:
                    agrouped_by_report_z[key] |= move

            for _z_key, report_moves in agrouped_by_report_z.items():
                range_start = 0
                range_last = 0
                cumulative = self._mf_init_cumulative()
                for index, move in enumerate(report_moves):
                    is_last_move = (index + 1) >= len(report_moves)
                    next_move = move if is_last_move else report_moves[index + 1]

                    amounts = self._determinate_amount_taxeds(move)
                    cumulative = self.update_amounts(cumulative, amounts)

                    if range_start == 0:
                        range_start = move.mf_invoice_number

                    if move.move_type not in ("out_invoice", "out_refund"):
                        continue

                    # Notas de débito: siempre línea individual.
                    if move.move_type == "out_invoice" and move.journal_id.is_debit:
                        sale_book_lines.append(self._fields_sale_book_line(move, amounts))
                        cumulative = self._mf_init_cumulative()
                        range_start = 0
                        continue

                    # Contribuyentes (J / especiales / no ordinarios) y notas de
                    # crédito: línea individual, cerrando antes el resumen abierto.
                    if (
                        move.partner_id.prefix_vat == "J"
                        or move.partner_id.taxpayer_type != "ordinary"
                        or move.move_type != "out_invoice"
                    ):
                        if cumulative["amount_taxed"] != amounts["amount_taxed"]:
                            data = {
                                "move_type": move.move_type,
                                "range_start": range_start,
                                "range_end": range_last or move.mf_invoice_number,
                                "date": move.invoice_date_display,
                                "mf_reportz": move.mf_reportz,
                                "mf_serial": move.mf_serial,
                            }
                            range_last = 0
                            sale_book_lines.append(
                                self._fields_sale_book_group_line(data, cumulative)
                            )
                        sale_book_lines.append(self._fields_sale_book_line(move, amounts))
                        cumulative = self._mf_init_cumulative()
                        range_start = 0
                        continue

                    # Consumidores finales ordinarios: se acumulan en el Resumen
                    # Diario y se emite una línea al cambiar de día/tipo/contribuyente.
                    if (
                        (
                            self._format_date(move.invoice_date_display)
                            != self._format_date(next_move.invoice_date_display)
                            or next_move.partner_id.prefix_vat == "J"
                            or next_move.partner_id.taxpayer_type != "ordinary"
                            or next_move.move_type != "out_invoice"
                            or is_last_move
                        )
                        and move.partner_id.taxpayer_type == "ordinary"
                    ):
                        data = {
                            "move_type": move.move_type,
                            "range_start": range_start,
                            "range_end": move.mf_invoice_number,
                            "date": move.invoice_date_display,
                            "mf_reportz": move.mf_reportz,
                            "mf_serial": move.mf_serial,
                        }
                        sale_book_lines.append(
                            self._fields_sale_book_group_line(data, cumulative)
                        )
                        cumulative = self._mf_init_cumulative()
                        range_start = 0
                        continue

                    range_last = move.mf_invoice_number

        return sale_book_lines
