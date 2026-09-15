import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)

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

    def _mf_mode(self):
        """Modo de reporte de máquina fiscal ACTIVO, o `None`. Solo aplica al
        Libro de Ventas: si el usuario marcó una casilla y luego cambió a
        Compras, la casilla queda oculta pero su valor NO se limpia, así que
        aquí se ignora (si no, el libro de compras saldría vacío exigiendo datos
        de MF). `all_documents` tiene prioridad (son excluyentes en la vista)."""
        if self.report != "sale":
            return None
        if self.all_documents:
            return "all_documents"
        if self.with_fiscal_machine:
            return "with_fiscal_machine"
        return None

    def _get_domain(self):
        domain = super()._get_domain()
        if self._mf_mode() != "with_fiscal_machine":
            return domain
        return self._fiscal_machine_domain(domain)

    # ------------------------------------------------------------------
    # Búsqueda de asientos
    # ------------------------------------------------------------------
    def _mf_sort_number(self, move):
        number = move.mf_invoice_number or ""
        return int(number) if number.isdigit() else 0

    def _only_fiscal_machine(self, moves):
        """Deja solo los asientos de maquina fiscal. Necesario porque otros
        modulos que extienden `search_moves` (p.ej. `l10n_ve_payment_extension`)
        inyectan asientos DESPUES del `super()`, ignorando `_get_domain()`; sin
        este re-filtro entrarian documentos sin datos de MF al libro fiscal."""
        return moves.filtered_domain(
            [
                ("mf_serial", "!=", False),
                ("mf_reportz", "!=", False),
                ("mf_invoice_number", "!=", False),
            ]
        )

    def search_moves(self):
        mode = self._mf_mode()
        if mode == "all_documents":
            # Forma libre (con nº de control) + maquina fiscal (sin nº de
            # control). Se parte de `super().search_moves()` para conservar lo
            # que aporten otros modulos al libro (retenciones de
            # payment_extension, etc.) y se une una segunda busqueda solo de
            # maquina fiscal, en vez de reemplazar la busqueda entera.
            domain_fiscal_machine = self._fiscal_machine_domain(super()._get_domain())
            moves = super().search_moves() | self.env["account.move"].search(
                domain_fiscal_machine
            )
            return moves.sorted(key=lambda m: m.invoice_date_display or m.date)
        if mode == "with_fiscal_machine":
            moves = self._only_fiscal_machine(super().search_moves())
            return moves.sorted(
                key=lambda m: (m.invoice_date_display or m.date, self._mf_sort_number(m))
            )
        return super().search_moves()

    # ------------------------------------------------------------------
    # Columnas extra de máquina fiscal en el libro de ventas
    # ------------------------------------------------------------------
    def _get_sale_book_field_groups(self):
        # "Con máquina fiscal": columnas iguales a las de V17 (una sola columna
        # "N° de documento" con el nº de máquina fiscal, columnas Reporte Z y
        # Serial, sin columnas de Alícuota %, y grupos VENTAS NACIONALES /
        # INTERNACIONALES). Se reconstruye la lista en vez de partir de la base
        # V19, porque el layout base de V19 es distinto.
        mode = self._mf_mode()
        if mode == "with_fiscal_machine":
            return self._fiscal_machine_sale_book_groups()

        # "Incluir todos los documentos": layout base V19 + columnas de MF.
        groups = super()._get_sale_book_field_groups()
        if mode != "all_documents":
            return groups

        extra_fields = [
            {"name": "N° Máquina Fiscal", "field": "mf_invoice_number", "size": 16},
            {"name": "Reporte Z", "field": "mf_reportz", "size": 16},
            {"name": "Serial de Máquina", "field": "mf_serial", "size": 16},
        ]

        detail_group = next(
            (g for g in groups if g.get("header") == "DETALLE DEL DOCUMENTO"), None
        )
        if detail_group is None:
            _logger.warning(
                "l10n_ve_account_mf: no se encontro el grupo 'DETALLE DEL "
                "DOCUMENTO' en el libro; las columnas de maquina fiscal no se "
                "insertaran. ¿Cambio el layout base de l10n_ve_invoice?"
            )
            return groups

        group_fields = detail_group["fields"]
        insertion_index = next(
            (
                i + 1
                for i, field_dict in enumerate(group_fields)
                if field_dict.get("field") == "move_type"
            ),
            None,
        )
        if insertion_index is None:
            _logger.warning(
                "l10n_ve_account_mf: no se encontro la columna 'move_type' en "
                "'DETALLE DEL DOCUMENTO'; las columnas de maquina fiscal no se "
                "insertaran."
            )
            return groups

        for offset, column in enumerate(extra_fields):
            group_fields.insert(insertion_index + offset, column)
        return groups

    def _fiscal_machine_sale_book_groups(self):
        """Columnas del libro de ventas "Con máquina fiscal", replicando el
        layout de V17."""
        company = self.company_id
        sale_groups = []

        basic_fields = [
            {"name": "N° operacion", "field": "index"},
            {"name": "Fecha del documento", "field": "document_date", "size": 16},
            {"name": "RIF", "field": "vat", "size": 16},
            {"name": "Nombre/Razón social", "field": "partner_name", "size": None},
            {"name": "Tipo", "field": "move_type", "size": 16},
            {"name": "Reporte Z", "field": "mf_reportz", "size": 16},
            {"name": "Serial de Maquina", "field": "mf_serial", "size": 16},
            {"name": "N° de documento", "field": "document_number", "size": 16},
            {"name": "N° de control", "field": "correlative", "size": 16},
            {"name": "Tipo de transacción", "field": "transaction_type"},
            {"name": "N° Factura afectada", "field": "number_invoice_affected", "size": 16},
        ]
        sale_groups.append({"header": "DETALLE DEL DOCUMENTO", "fields": basic_fields})

        total_fields = [
            {"name": "Total ventas", "field": "total_sales", "format": "number", "size": 16},
            {"name": "Total ventas con IVA", "field": "total_sales_iva", "format": "number", "size": 16},
            {"name": "Total ventas exentas", "field": "total_sales_not_iva", "format": "number", "size": 16},
        ]
        sale_groups.append({"header": "TOTALES", "fields": total_fields})

        national_fields = [
            {"name": "Base imponible (16%)", "field": "tax_base_general_aliquot", "format": "number", "size": 16},
            {"name": "IVA 16%", "field": "amount_general_aliquot", "format": "number", "size": 16},
        ]
        if not company.not_show_reduced_aliquot_sale:
            national_fields.extend([
                {"name": "Base imponible (8%)", "field": "tax_base_reduced_aliquot", "format": "number"},
                {"name": "IVA 8%", "field": "amount_reduced_aliquot", "format": "number"},
            ])
        if not company.not_show_extend_aliquot_sale:
            national_fields.extend([
                {"name": "Base imponible (31%)", "field": "tax_base_extend_aliquot", "format": "number"},
                {"name": "IVA 31%", "field": "amount_extend_aliquot", "format": "number"},
            ])
        sale_groups.append({"header": "VENTAS NACIONALES", "fields": national_fields})

        international_fields = [
            {"name": "Base imponible", "field": "tax_base_zero_aliquot_international", "format": "number"},
            {"name": "Alicuota 0%", "field": "zero_aliquot_international", "format": "percent"},
            {"name": "IVA 0%", "field": "amount_zero_aliquot_international", "format": "number"},
        ]
        sale_groups.append({"header": "VENTAS INTERNACIONALES", "fields": international_fields})

        # Anexar los grupos que aportan OTROS módulos (IGTF, RETENCIONES, etc.),
        # que en V19 vienen del layout base ALÍCUOTA y se perderían al reconstruir
        # las columnas desde cero. Se toman de super() y se añaden al final, en el
        # mismo orden que V17 (IGTF, RETENCIONES).
        replaced_headers = {
            "DETALLE DEL DOCUMENTO",
            "TOTALES",
            "ALÍCUOTA GENERAL (16%)",
            "ALÍCUOTA REDUCIDA (8%)",
            "ALÍCUOTA ADICIONAL (31%)",
        }
        for group in super()._get_sale_book_field_groups():
            if group.get("header") not in replaced_headers:
                sale_groups.append(group)

        return sale_groups

    def _fields_sale_book_line(self, move, taxes):
        res = super()._fields_sale_book_line(move, taxes)
        mode = self._mf_mode()
        if mode is None:
            return res

        res["mf_reportz"] = move.mf_reportz or "-"
        res["mf_serial"] = move.mf_serial or "-"
        if move.reversed_entry_id and move.reversed_entry_id.mf_invoice_number:
            res["number_invoice_affected"] = move.reversed_entry_id.mf_invoice_number

        if mode == "with_fiscal_machine":
            # Layout V17: nº MF en "N° de documento", sin nº de control, con
            # columnas de venta internacional (0%) en cero.
            res["document_number"] = move.mf_invoice_number or ""
            res["correlative"] = ""
            res["tax_base_zero_aliquot_international"] = 0
            res["zero_aliquot_international"] = 0
            res["amount_zero_aliquot_international"] = 0
        else:
            # Layout "todos los documentos": columna propia con el nº MF.
            res["mf_invoice_number"] = move.mf_invoice_number or "-"
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

    def _mf_update_amounts(self, cumulative, amounts):
        return {
            key: cumulative.get(key, 0) + amounts.get(key, 0)
            for key in self._MF_AMOUNT_KEYS
        }

    def _fields_sale_book_group_line(self, data, amounts):
        # Línea de Resumen Diario, con el layout de columnas de V17.
        amount_taxed = amounts.get("amount_taxed", 0)
        exempt = amounts.get("tax_base_exempt_aliquot", 0)
        return {
            "document_date": self._format_date(data.get("date")),
            "accounting_date": self._format_date(data.get("date")),
            "vat": "RESUMEN",
            "partner_name": "Resumen Diario de Ventas",
            "move_type": self._determinate_type(data.get("move_type")),
            "document_number": f"Desde {data.get('range_start')} Hasta {data.get('range_end')}",
            "correlative": "",
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
            "tax_base_zero_aliquot_international": 0,
            "zero_aliquot_international": 0,
            "amount_zero_aliquot_international": 0,
            "igtf": 0,
        }

    def _mf_is_individual_move(self, move):
        """Un asiento sale en linea propia (no colapsado en el Resumen Diario)
        si es nota de credito, nota de debito, o de un contribuyente RIF "J" /
        especial / no ordinario. Solo los consumidores finales ordinarios se
        acumulan en el resumen."""
        return (
            move.move_type != "out_invoice"
            or move.journal_id.is_debit
            or move.partner_id.prefix_vat == "J"
            or move.partner_id.taxpayer_type != "ordinary"
        )

    def _mf_parse_report_z(self, report_moves):
        """Lineas del libro para UN Reporte Z: los consumidores finales
        ordinarios se colapsan en lineas de Resumen Diario por rango de numero
        de maquina; los contribuyentes, notas de credito y notas de debito
        salen linea a linea. El resumen abierto se cierra ANTES de cada linea
        individual y al terminar el Reporte Z."""
        lines = []
        summary = self._mf_init_cumulative()
        range_start = 0
        range_last = 0
        has_open_summary = False
        summary_ref = self.env["account.move"]

        def flush():
            # Emite la linea de Resumen con lo acumulado (sin incluir ningun
            # asiento individual: aqui solo llegan ordinarios) y reinicia estado.
            nonlocal summary, range_start, range_last, has_open_summary, summary_ref
            if not has_open_summary:
                return
            data = {
                "move_type": "out_invoice",
                "range_start": range_start,
                "range_end": range_last or range_start,
                "date": summary_ref.invoice_date_display,
                "mf_reportz": summary_ref.mf_reportz,
                "mf_serial": summary_ref.mf_serial,
            }
            lines.append(self._fields_sale_book_group_line(data, summary))
            summary = self._mf_init_cumulative()
            range_start = 0
            range_last = 0
            has_open_summary = False
            summary_ref = self.env["account.move"]

        for move in report_moves:
            amounts = self._determinate_amount_taxeds(move)

            if self._mf_is_individual_move(move):
                flush()  # cerrar el resumen de ordinarios que quede abierto
                lines.append(self._fields_sale_book_line(move, amounts))
                continue

            # Consumidor final ordinario: acumular en el Resumen Diario.
            summary = self._mf_update_amounts(summary, amounts)
            if not has_open_summary:
                range_start = move.mf_invoice_number
                has_open_summary = True
            range_last = move.mf_invoice_number
            summary_ref = move

        flush()  # resumen que quede abierto al final del Reporte Z
        return lines

    def parse_sale_book_data(self):
        # all_documents y forma libre: linea por linea (comportamiento base, con
        # las columnas de MF que añade _fields_sale_book_line).
        if self._mf_mode() != "with_fiscal_machine":
            return super().parse_sale_book_data()

        sale_book_lines = []
        moves = self.search_moves()

        # Agrupar por dia (fecha del DOCUMENTO, no `create_date`, que esta en UTC
        # y arrastraria las ventas nocturnas al bucket del dia siguiente) y luego
        # por Reporte Z.
        agrouped_by_date = {}
        for move in moves:
            key = move.invoice_date_display or move.date
            agrouped_by_date.setdefault(key, self.env["account.move"])
            agrouped_by_date[key] |= move

        for _date_key in sorted(agrouped_by_date):
            date_moves = agrouped_by_date[_date_key]
            agrouped_by_report_z = {}
            for move in date_moves.sorted(self._mf_sort_number):
                key = f"{move.mf_serial}_{move.mf_reportz}"
                agrouped_by_report_z.setdefault(key, self.env["account.move"])
                agrouped_by_report_z[key] |= move

            for _z_key, report_moves in agrouped_by_report_z.items():
                sale_book_lines += self._mf_parse_report_z(report_moves)

        return sale_book_lines
