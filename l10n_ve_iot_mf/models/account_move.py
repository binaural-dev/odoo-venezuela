from odoo import fields, models, api, _
from odoo.exceptions import ValidationError,UserError
import re
import unicodedata

import logging

_logger = logging.getLogger(__name__)


class AccountMoveInh(models.Model):
    _inherit = "account.move"

    def default_fiscal_machine(self):
        """
        Return unique fiscal machine on IoT Box
        """
        return self.env["iot.device"].search([("type", "=", "fiscal_data_module")], limit=1).id

    is_credit = fields.Boolean(default=False)
    iot_mf = fields.Many2one(
        "iot.device",
        string="Fiscal Machine",
        default=default_fiscal_machine,
        copy=False,
        domain=[("serial_machine", "!=", False)],
    )
    iot_box = fields.Many2one(
        "iot.box", string="IoT Box", related="iot_mf.iot_id", default=False, copy=False
    )
    mf_serial = fields.Char(
        string="Fiscal machine serial", default=False, copy=False, tracking=True
    )
    mf_invoice_number = fields.Char(
        string="Sequence number", default=False, copy=False, tracking=True
    )
    mf_reportz = fields.Char(string="Report number Z", default=False, copy=False, tracking=True)
    # Ticket 16293: el documento salió impreso (cierre aceptado por la
    # máquina) pero no se pudo leer S1, así que no hay número/serial/Z.
    # Mientras esté marcado no se puede volver a imprimir (se duplicaría el
    # documento fiscal) y se ofrece recuperar los datos leyendo S1.
    mf_pending_sync = fields.Boolean(
        string="Datos fiscales por recuperar", default=False, copy=False, readonly=True, tracking=True
    )
    # Foto de S1 tomada justo antes de imprimir: {doc_type, number_before,
    # serial, z_before}. Permite atribuir sin ambigüedad el número que la
    # máquina asignó a este documento.
    mf_pending_sync_data = fields.Json(copy=False, readonly=True)
    
    def _default_print_type(self):
        return self.env.company.invoice_print_type

    print_type = fields.Selection(
        selection=lambda self: self.env['res.company']._fields['invoice_print_type'].selection,
        default=_default_print_type,
        store=True,
    )

    def has_printed(self, invoice_number):
        """
        Check if the invoice sequence has already been printed
        -----------
        Return
        Recordset of account.move if exist
        """
        if not invoice_number:
            return False
        
        return (
            len(
                self.env["account.move"].search(
                    [("mf_invoice_number", "=", invoice_number)], limit=2
                )
            )
            > 1
        )

    def check_report_z(self, serial):
        account_moves = self.env["account.move"].search(
            ["&", ("mf_serial", "=", serial), ("mf_reportz", "=", False)]
        )

        return bool(account_moves)

    def report_z(self, serial, response):
        # El driver del IoT puede resolver el listener con un evento valido
        # que aun no trae "data" (ACK de comando recibido, antes de que la
        # impresora termine el Z fisico). data debe degradar a {} para no
        # reventar con 'bool' object has no attribute 'get' — este es el
        # crash del ticket 13283, y ocurre AQUI (implementacion raiz), no en
        # l10n_ve_pos_mf.
        data = response.get("data") or {}

        if not response.get("valid", False):
            raise ValidationError(response.get("message", "No se pudo imprimir el reporte Z"))

        # Sin data del dispositivo, el serial recibido como parametro es la
        # unica referencia de maquina disponible.
        serial = data.get("_registeredMachineNumber") or serial

        last_z_number = self._get_last_z_number(serial)
        account_moves = self.env["account.move"].search(
            [("mf_serial", "=", serial), ("mf_reportz", "=", False)]
        )
        last_number = (
            self._max_mf_invoice_number_for_z(serial, last_z_number)
            if last_z_number is not None
            else None
        )
        account_moves = account_moves.filtered(
            lambda m: self._mf_invoice_number_after(m, last_number)
        )

        _dailyClosureCounter = data.get("_dailyClosureCounter")
        if _dailyClosureCounter in (False, None):
            _logger.info("NO SE RECUPERO EL Z DE LA MAQUINA: %s", serial)
            _numberOfLastZReport = (last_z_number or 0) + 1
            _logger.info("ULTIMO Z: %s", _numberOfLastZReport)
        else:
            _numberOfLastZReport = int(_dailyClosureCounter)

        for invoice in account_moves:
            invoice.write({"mf_reportz": _numberOfLastZReport})
        return _numberOfLastZReport

    def _parse_mf_invoice_number(self, move):
        try:
            return int(move.mf_invoice_number)
        except (TypeError, ValueError):
            return None

    def _mf_invoice_number_after(self, move, last_number):
        number = self._parse_mf_invoice_number(move)
        if number is None:
            return False
        if last_number is None:
            return True
        return number > last_number

    def _get_last_z_number(self, serial):
        self.env.cr.execute(
            """
            SELECT MAX(
                CASE WHEN mf_reportz ~ '^[0-9]+$'
                     THEN mf_reportz::integer
                     ELSE NULL
                END
            )
            FROM account_move
            WHERE mf_serial = %s AND company_id = %s
            """,
            (serial, self.env.company.id),
        )
        return self.env.cr.fetchone()[0]

    def _max_mf_invoice_number_for_z(self, serial, z_number):
        moves = self.env["account.move"].search(
            [("mf_serial", "=", serial), ("mf_reportz", "=", str(z_number))]
        )
        numbers = [n for n in (self._parse_mf_invoice_number(m) for m in moves) if n is not None]
        return max(numbers) if numbers else None

    @api.onchange("is_credit")
    def _onchange_is_credit(self):
        for i in self:
            if i.mf_invoice_number:
                raise ValidationError(_("You can't edit a paper invoice"))
            if i.is_credit:
                if i.amount_residual != i.amount_total:
                    raise ValidationError(
                        _("You cannot convert an invoice to credit if it has associated payments")
                    )

    def _find_iot_mf_by_serial(self, serial):
        """Busca el dispositivo IoT fiscal por serial de máquina."""
        if not serial:
            return self.env["iot.device"]
        return self.env["iot.device"].search(
            [("type", "=", "fiscal_data_module"), ("serial_machine", "=", serial)], limit=1
        )

    def _mf_persist_vals(self, result_data):
        """Construye los vals fiscales a persistir tras una impresión Web Serial.

        Incluye mf_invoice_number, mf_serial, mf_reportz (si viene) y asocia
        iot_mf por serial. Si no existe iot.device con ese serial, no bloquea:
        deja advertencia en el chatter.
        """
        self.ensure_one()
        sequence = result_data.get("sequence")
        serial_machine = result_data.get("serial_machine")

        vals = {
            "mf_invoice_number": sequence,
            "mf_serial": serial_machine,
        }
        if result_data.get("mf_reportz"):
            vals["mf_reportz"] = result_data["mf_reportz"]

        iot_device = self._find_iot_mf_by_serial(serial_machine)
        if iot_device:
            vals["iot_mf"] = iot_device.id
        else:
            _logger.warning(
                "l10n_ve_iot_mf: no se encontró iot.device fiscal con serial %s "
                "para asociar en %s (id %s)",
                serial_machine,
                self.name,
                self.id,
            )
            self.message_post(
                body=_(
                    "Se imprimió fiscalmente (Nro. %(sequence)s, serial %(serial)s), "
                    "pero no se pudo asociar el dispositivo de máquina fiscal (iot_mf) "
                    "porque no existe un dispositivo registrado con ese serial.",
                    sequence=sequence or "-",
                    serial=serial_machine or "-",
                )
            )
        return vals

    def _mf_action_label(self, action):
        action_labels = {
            "print_out_invoice": _("Factura"),
            "print_out_refund": _("Nota de crédito"),
            "print_debit_note": _("Nota de débito"),
            "reprint_document": _("Reimpresión"),
            "sync_fiscal_data": _("Recuperación de datos fiscales"),
        }
        return action_labels.get(action, action or _("Documento fiscal"))

    def log_mf_print_failure(self, action=None, reason=None, kind=None):
        """Deja constancia en el chatter de un intento fallido de impresión fiscal.

        Llamado desde el frontend Web Serial cuando no hay conexión con la
        máquina fiscal o el driver reporta un error.

        :param kind: "no_connection" cuando no se pudo hablar con la máquina.
            Cualquier otro valor (o None) es un error durante la operación: el
            mensaje ya no afirma que "no hay máquina fiscal conectada", porque
            eso era falso cuando el error ocurría con la máquina respondiendo
            (ticket 16293).
        """
        label = self._mf_action_label(action)
        if kind == "no_connection":
            body = _(
                "No se ha impreso en máquina fiscal (%(label)s) porque no hay "
                "conexión con la máquina fiscal.",
                label=label,
            )
        else:
            body = _(
                "No se ha impreso en máquina fiscal (%(label)s): la máquina fiscal reportó un error.",
                label=label,
            )
        if reason:
            body += _(" Detalle: %(reason)s", reason=reason)
        for move in self:
            move.message_post(body=body)
        return True

    # ------------------------------------------------------------------
    # Ticket 16293: documento impreso sin datos fiscales (S1 ilegible)
    # ------------------------------------------------------------------

    _MF_S1_NUMBER_KEYS = {
        "invoice": "last_invoice_number",
        "credit_note": "last_nc_number",
        "debit_note": "last_debit_note_number",
    }

    def _mf_doc_type(self):
        self.ensure_one()
        if self.move_type == "out_refund":
            return "credit_note"
        if self.is_debit_journal:
            return "debit_note"
        return "invoice"

    @staticmethod
    def _mf_to_int(value):
        if value in (None, False, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _mf_check_not_pending(self):
        for move in self:
            if move.mf_pending_sync:
                raise ValidationError(
                    _(
                        "Este documento ya se imprimió en la máquina fiscal, pero faltan sus datos "
                        "fiscales. No lo vuelva a imprimir: use \"Recuperar datos fiscales (MF)\"."
                    )
                )

    def mf_mark_pending_sync(self, action=None, reason=None, before=None):
        """Marca el documento como impreso sin datos fiscales.

        Lo llama el botón Web Serial cuando el driver informa que la máquina
        aceptó el cierre del documento (salió impreso) pero no pudo leer S1.

        :param before: foto de S1 tomada antes de imprimir, con las claves
            last_invoice_number, last_nc_number, last_debit_note_number,
            serial y daily_closure_counter. Puede venir vacía si esa lectura
            también falló.
        """
        self.ensure_one()
        before = before or {}
        doc_type = self._mf_doc_type()
        data = {
            "doc_type": doc_type,
            "number_before": self._mf_to_int(before.get(self._MF_S1_NUMBER_KEYS[doc_type])),
            "serial": before.get("serial") or False,
            "z_before": self._mf_to_int(before.get("daily_closure_counter")),
        }
        self.write({"mf_pending_sync": True, "mf_pending_sync_data": data})

        body = _(
            "%(label)s impresa en la máquina fiscal, pero no se pudieron leer sus datos fiscales "
            "(número, serial y reporte Z). No la vuelva a imprimir: use \"Recuperar datos "
            "fiscales (MF)\" con la máquina conectada.",
            label=self._mf_action_label(action),
        )
        if reason:
            body += _(" Detalle: %(reason)s", reason=reason)
        self.message_post(body=body)
        return True

    def write(self, vals):
        res = super().write(vals)
        if vals.get("mf_invoice_number"):
            # Carga manual de los datos fiscales de un documento pendiente
            # (casos que mf_sync_fiscal_data no puede atribuir solo).
            synced = self.filtered(lambda m: m.mf_pending_sync and m.mf_invoice_number)
            if synced:
                synced.write({"mf_pending_sync": False, "mf_pending_sync_data": False})
        return res

    def check_mf_sync(self):
        """Valida que se puedan recuperar los datos fiscales del documento."""
        self.ensure_one()
        if not self.mf_pending_sync:
            raise ValidationError(_("Este documento no tiene datos fiscales pendientes por recuperar."))
        if self.mf_invoice_number:
            raise ValidationError(_("El documento ya tiene número fiscal."))
        return {"valid": True, "doc_type": (self.mf_pending_sync_data or {}).get("doc_type")}

    def mf_sync_fiscal_data(self, s1):
        """Asigna los datos fiscales de un documento impreso sin ellos.

        Compara S1 actual con la foto tomada antes de imprimir. Solo asigna
        el número cuando el contador avanzó exactamente uno: si avanzó más,
        se imprimieron otros documentos en el medio y el número no se puede
        atribuir con certeza; si no avanzó, los datos se contradicen con el
        cierre aceptado. En ambos casos se pide revisión manual en vez de
        adivinar, porque un número equivocado deja el libro de ventas mal.

        :param s1: S1 actual, mismas claves que ``before`` en
            :meth:`mf_mark_pending_sync`.
        :returns: dict con el número, serial y Z asignados.
        """
        self.ensure_one()
        self.check_mf_sync()
        s1 = s1 or {}
        pending = self.mf_pending_sync_data or {}
        doc_type = pending.get("doc_type") or self._mf_doc_type()

        serial = s1.get("serial") or False
        if not serial:
            raise UserError(_("La máquina fiscal no devolvió su serial. Intente de nuevo."))
        if pending.get("serial") and pending["serial"] != serial:
            raise UserError(
                _(
                    "La máquina conectada (serial %(now)s) no es la que imprimió el documento "
                    "(serial %(before)s). Conecte la máquina correcta.",
                    now=serial,
                    before=pending["serial"],
                )
            )

        number_now = self._mf_to_int(s1.get(self._MF_S1_NUMBER_KEYS[doc_type]))
        if number_now is None:
            raise UserError(_("La máquina fiscal no devolvió el último número del documento. Intente de nuevo."))

        number_before = pending.get("number_before")
        if number_before is None:
            raise UserError(
                _(
                    "No hay una lectura de la máquina previa a la impresión, así que no se puede "
                    "saber con certeza qué número le asignó. El último número de la máquina es "
                    "%(number)s: verifíquelo contra el documento impreso y cárguelo manualmente en la sección Máquina Fiscal.",
                    number=number_now,
                )
            )
        if number_now == number_before:
            raise UserError(
                _(
                    "La máquina aceptó el cierre del documento, pero su contador no avanzó "
                    "(sigue en %(number)s). Revise el documento impreso antes de continuar.",
                    number=number_now,
                )
            )
        if number_now != number_before + 1:
            raise UserError(
                _(
                    "Después de este documento se imprimieron otros en la máquina (el contador "
                    "pasó de %(before)s a %(now)s). El número de este documento debería ser "
                    "%(expected)s: verifíquelo contra el documento impreso y cárguelo manualmente en la sección Máquina Fiscal.",
                    before=number_before,
                    now=number_now,
                    expected=number_before + 1,
                )
            )

        sequence = str(number_now)
        duplicate = self.search(
            [
                ("id", "!=", self.id),
                ("company_id", "=", self.company_id.id),
                ("mf_serial", "=", serial),
                ("mf_invoice_number", "=", sequence),
                ("move_type", "=", self.move_type),
                ("is_debit_journal", "=", self.is_debit_journal),
            ],
            limit=1,
        )
        if duplicate:
            raise UserError(
                _(
                    "El número fiscal %(number)s ya está asignado a %(move)s.",
                    number=sequence,
                    move=duplicate.display_name,
                )
            )

        # El Z del documento es el abierto cuando se imprimió (el de la foto),
        # aunque se haya cerrado un Z entre la impresión y la recuperación.
        z_counter = pending.get("z_before")
        if z_counter is None:
            z_counter = self._mf_to_int(s1.get("daily_closure_counter"))
        mf_reportz = str(z_counter + 1) if z_counter is not None else False

        vals = self._mf_persist_vals(
            {"sequence": sequence, "serial_machine": serial, "mf_reportz": mf_reportz}
        )
        vals.update({"mf_pending_sync": False, "mf_pending_sync_data": False})
        self.write(vals)
        self.message_post(
            body=_(
                "Datos fiscales recuperados de la máquina: número %(number)s, serial %(serial)s, "
                "reporte Z %(z)s.",
                number=sequence,
                serial=serial,
                z=mf_reportz or "-",
            )
        )
        return {"sequence": sequence, "serial_machine": serial, "mf_reportz": mf_reportz}

    def _get_mf_flag21(self):
        """Flag 21 (formato numérico TFHKA) para impresión Web Serial.

        Prioridad: dispositivo IoT legacy (si existe) > configuración de la
        compañía > default "00".
        """
        self.ensure_one()
        if self.iot_mf and self.iot_mf.flag_21:
            return self.iot_mf.flag_21
        return self.company_id.mf_flag_21 or "00"

    def check_reprint(self):
        if not self.mf_invoice_number:
            raise ValidationError(_("The invoice has not already been printed"))
        data = self
        if not data:
            return {"valid": False, "message": "No se envio datos"}

        if not data.invoice_line_ids:
            return {"valid": False, "message": "La factura no tiene lineas"}

        _data = {
            # identifier/iot_ip: legacy IoT, se mantienen por compatibilidad con overrides
            "identifier": data.iot_mf.identifier if data.iot_mf else False,
            "iot_ip": data.iot_box.ip if data.iot_box else False,
            "type": data.move_type,
            "mf_number": data.mf_invoice_number,
            "is_debit_note": data.is_debit_journal
        }
        return _data

    def _get_mf_document_date(self):
        """Fecha real del documento fiscal: usada para validar que la
        impresion ocurra el mismo dia, y como fecha impresa de la factura
        referenciada en notas de credito/debito. Clientes donde invoice_date
        cumple doble funcion (fecha de tasa + fecha de factura) deben
        sobreescribir este metodo con su propio campo de fecha de factura."""
        return self.invoice_date

    def check_print_out_invoice(self):
        # if not self.journal_id.fiscal:
        #     raise ValidationError(_("You cannot print an invoice with a non-fiscal journal"))
        self._mf_check_not_pending()
        try:
            if self.mf_invoice_number:
                raise ValidationError(_("The invoice has already been printed"))
            if self.state in ["draft", "cancel"]:
                raise ValidationError(_("Cannot print an invoice without validation"))
            if self._get_mf_document_date() != fields.Date.context_today(self):
                raise ValidationError(_("Cannot print an invoice with a future date"))
            if self.is_credit and self.amount_residual != self.amount_total:
                raise ValidationError(_("You cannot print a credit invoice with associated payments"))

            data = self

            if not data:
                return {"valid": False, "message": "No se envio datos"}

            if not data.invoice_line_ids:
                return {"valid": False, "message": "La factura no tiene lineas"}

            payment_lines = []
            payments = data.invoice_payments_widget

            if not payments:
                payment_lines.append({"amount": 0, "payment_method": "01"})
            else:
                payments = payments["content"]
                for payment in payments:
                    journal_id = self.env["account.journal"].search(
                        [("name", "=", payment["journal_name"])], limit=1
                    )
                    new_payment = {
                        "amount": payment["amount"],
                        "payment_method": journal_id["payment_method"] or "01",
                    }
                    if payment["currency_id"] != data.env.ref("base.VEF").id:
                        new_payment["amount"] = payment["amount"] * data.foreign_inverse_rate

                    payment_lines.append(new_payment)

            _invoice_lines = []

            for line in data.invoice_line_ids:
                price_vef = line.price_unit
                if data.company_id.currency_id.id != data.env.ref("base.VEF").id:
                    price_vef = line.foreign_price
                # Aplicar descuento % de la línea (Facturación/Contabilidad).
                # El formateo/redondeo final lo hace el driver Web Serial.
                if line.discount:
                    price_vef = price_vef * (1 - line.discount / 100.0)
                _invoice_lines.append(
                    {
                        "tax": line.tax_ids[0].fiscal_code if line.tax_ids else 0,
                        "price_unit": price_vef,
                        "quantity": line.quantity,
                        "code": False,
                        "name": f"[{line.product_id.default_code}] {self._normalize_product_name(line.product_id.name)}"
                        if line.product_id
                        else self._normalize_product_name(line.name),
                    }
                )

            _data = {
                "flag_21": data._get_mf_flag21(),
                "identifier": data.iot_mf.identifier if data.iot_mf else False,
                "iot_ip": data.iot_box.ip if data.iot_box else False,
                "company_id": {"name": data.company_id.name},
                "partner_id": {
                    "name": self._normalize_product_name(data.partner_id.name),
                    "vat": f"{data.partner_id.prefix_vat}-{data.partner_id.vat}",
                    "address": data.partner_id.street or False,
                    "phone": data.partner_id.phone or False,
                },
                "invoice_lines": _invoice_lines,
                "payment_lines": payment_lines,
                "max_razon_social": data.iot_mf.max_razon_social or 40,
            }
            return _data
        
        except ValidationError as ae:
            raise ValidationError(str(ae))

    def print_out_invoice(self, values):
        _logger.info("VALUE %s", values)
        result_data = values.get("data", {})
        sequence = result_data.get("sequence")

        self.write(self._mf_persist_vals(result_data))

        if self.has_printed(sequence):
            context = dict(self._context or {})
            context[
                "message"
            ] = f"""
            An invoice with the same sequence number {sequence}
            Please review previous invoices
            """

            return {
                "name": f"Warning",
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": "sh.message.wizard",
                "target": "new",
                "context": context,
            }
            
    def check_print_out_refund(self):
        """
        Print out refund in fiscal machine
        """
        self._mf_check_not_pending()
        try:
            if self.mf_invoice_number:
                raise ValidationError(_("The invoice has already been printed"))
            # if self.iot_mf.serial_machine != self.reversed_entry_id.mf_serial:
            #     raise ValidationError(_("The credit note must be made in the same fiscal machine"))
            if self._get_mf_document_date() != fields.Date.context_today(self):
                raise ValidationError(_("The credit note must be made on the same day"))
            if self.state in ["draft", "cancel"]:
                raise ValidationError(_("Cannot print an invoice without validation"))

            data = self

            if not data:
                return {"valid": False, "message": "No se envio datos"}

            if not data.invoice_line_ids:
                return {"valid": False, "message": "La factura no tiene lineas"}

            payment_lines = []

            # En NC PoS, usar pagos reales de la orden para no perder
            # separación por método fiscal (el widget puede agrupar).
            # Buscar por el move actual y también por la factura afectada
            # (caso común de reverso donde la NC no queda como account_move del pos.order).
            candidate_move_ids = [data.id]
            if data.reversed_entry_id:
                candidate_move_ids.append(data.reversed_entry_id.id)

            pos_order = self.env["pos.order"].search(
                [("account_move", "in", candidate_move_ids)],
                order="id desc",
                limit=1,
            ) if "pos.order" in self.env.registry else False

            if pos_order and pos_order.payment_ids:
                for payment in pos_order.payment_ids:
                    fiscal_method = (
                        payment.payment_method_id.code_fiscal_printer
                        or payment.payment_method_id.journal_id.payment_method
                        or "01"
                    )
                    payment_lines.append(
                        {
                            "amount": abs(payment.amount or 0.0),
                            "payment_method": fiscal_method,
                        }
                    )
            else:
                payments = data.invoice_payments_widget
                if not payments:
                    payment_lines.append({"amount": 0, "payment_method": "01"})
                else:
                    payments = payments["content"]
                    for payment in payments:
                        journal_id = self.env["account.journal"].search(
                            [("name", "=", payment["journal_name"])], limit=1
                        )
                        new_payment = {
                            "amount": abs(payment["amount"]),
                            "payment_method": journal_id["payment_method"] or "01",
                        }
                        if payment["currency_id"] != data.env.ref("base.VEF").id:
                            new_payment["amount"] = abs(payment["amount"]) * data.foreign_inverse_rate

                        payment_lines.append(new_payment)

            _invoice_lines = []
            for line in data.invoice_line_ids:
                price_vef = line.price_unit
                if data.company_id.currency_id.id != data.env.ref("base.VEF").id:
                    price_vef = line.foreign_price
                # Aplicar descuento % de la línea (Facturación/Contabilidad).
                # El formateo/redondeo final lo hace el driver Web Serial.
                if line.discount:
                    price_vef = price_vef * (1 - line.discount / 100.0)
                _invoice_lines.append(
                    {
                        "tax": line.tax_ids[0].fiscal_code if line.tax_ids else 0,
                        "price_unit": price_vef,
                        "quantity": line.quantity,
                        "code": False,
                        "name": f"[{line.product_id.default_code}] {self._normalize_product_name(line.product_id.name)}"
                        if line.product_id
                        else self._normalize_product_name(line.name),
                    }
                )

            _data = {
                "flag_21": data._get_mf_flag21(),
                "identifier": data.iot_mf.identifier if data.iot_mf else False,
                "iot_ip": data.iot_box.ip if data.iot_box else False,
                "company_id": {"name": data.company_id.name},
                "partner_id": {
                    "name": self._normalize_product_name(data.partner_id.name),
                    "vat": f"{data.partner_id.prefix_vat}-{data.partner_id.vat}",
                    "address": data.partner_id.street or False,
                    "phone": data.partner_id.phone or False,
                },
                "invoice_affected": {
                    "number": data.reversed_entry_id.mf_invoice_number,
                    "serial_machine": data.reversed_entry_id.mf_serial,
                    "date": data.reversed_entry_id._get_mf_document_date().strftime("%d/%m/%Y"),
                },
                "invoice_lines": _invoice_lines,
                "payment_lines": payment_lines,
                "max_razon_social": data.iot_mf.max_razon_social or 40,
            }

            return _data
        
        except ValidationError as ae:
            raise ValidationError(str(ae))
        
    def print_out_refund(self, values):
        _logger.info("VALUE %s", values)
        result_data = values.get("data", {})

        self.write(self._mf_persist_vals(result_data))

    def _get_reconciled_info_JSON_values(self):
        res = super()._get_reconciled_info_JSON_values()
        reconciled_vals = []
        for payment in res:
            payment_id = self.env["account.payment"].search(
                [("id", "=", payment["account_payment_id"])]
            )
            payment["mf_payment_method"] = payment_id.journal_id.payment_method
            reconciled_vals.append(payment)
        return reconciled_vals

        
    def check_print_debit_note(self):
        """
        Print debit note in fiscal machine
        """
        self._mf_check_not_pending()
        try:
            if self.mf_invoice_number:
                raise ValidationError(_("The invoice has already been printed"))
            # if self.iot_mf.serial_machine != self.debit_origin_id.mf_serial:
            #     raise ValidationError(_("The debit note must be made in the same fiscal machine"))
            if self._get_mf_document_date() != fields.Date.context_today(self):
                raise ValidationError(_("The debit note must be made on the same day"))
            if self.state in ["draft", "cancel"]:
                raise ValidationError(_("Cannot print an invoice without validation"))

            data = self

            if not data:
                return {"valid": False, "message": "No se envio datos"}

            if not data.invoice_line_ids:
                return {"valid": False, "message": "La factura no tiene lineas"}

            payment_lines = []
            payments = data.invoice_payments_widget

            if not payments:
                payment_lines.append({"amount": 0, "payment_method": "01"})
            else:
                payments = payments["content"]
                for payment in payments:
                    journal_id = self.env["account.journal"].search(
                        [("name", "=", payment["journal_name"])], limit=1
                    )
                    new_payment = {
                        "amount": payment["amount"],
                        "payment_method": journal_id["payment_method"] or "01",
                    }
                    if payment["currency_id"] != data.env.ref("base.VEF").id:
                        new_payment["amount"] = payment["amount"] * data.foreign_inverse_rate

                    payment_lines.append(new_payment)

            _invoice_lines = []
            for line in data.invoice_line_ids:
                price_vef = line.price_unit
                if data.company_id.currency_id.id != data.env.ref("base.VEF").id:
                    price_vef = line.foreign_price
                # Aplicar descuento % de la línea (Facturación/Contabilidad).
                # El formateo/redondeo final lo hace el driver Web Serial.
                if line.discount:
                    price_vef = price_vef * (1 - line.discount / 100.0)
                _invoice_lines.append(
                    {
                        "tax": line.tax_ids[0].fiscal_code if line.tax_ids else 0,
                        "price_unit": price_vef,
                        "quantity": line.quantity,
                        "code": False,
                        "name": f"[{line.product_id.default_code}] {self._normalize_product_name(line.product_id.name)}"
                        if line.product_id
                        else self._normalize_product_name(line.name),
                    }
                )

            _data = {
                "flag_21": data._get_mf_flag21(),
                "identifier": data.iot_mf.identifier if data.iot_mf else False,
                "iot_ip": data.iot_box.ip if data.iot_box else False,
                "company_id": {"name": data.company_id.name},
                "partner_id": {
                    "name": self._normalize_product_name(data.partner_id.name),
                    "vat": f"{data.partner_id.prefix_vat}-{data.partner_id.vat}",
                    "address": data.partner_id.street or False,
                    "phone": data.partner_id.phone or False,
                },
                "invoice_affected": {
                    "number": data.debit_origin_id.mf_invoice_number,
                    "serial_machine": data.debit_origin_id.mf_serial,
                    "date": data.debit_origin_id._get_mf_document_date().strftime("%d/%m/%Y"),
                },
                "invoice_lines": _invoice_lines,
                "payment_lines": payment_lines,
                "max_razon_social": data.iot_mf.max_razon_social or 40,
            }

            return _data
        
        except ValidationError as ae:
            raise ValidationError(str(ae))
        
        
    def print_debit_note(self, values):
        _logger.info("VALUE %s", values)
        result_data = values.get("data", {})

        self.write(self._mf_persist_vals(result_data))
        

    def _normalize_product_name(self, name):
        if not name:
            return ""
        
        normalized = unicodedata.normalize('NFKD', str(name))

        no_accents = ''.join(c for c in normalized if not unicodedata.combining(c))
        
        cleaned = re.sub(r'[^\w\s]', ' ', no_accents)
        
        final_name = re.sub(r'\s+', ' ', cleaned).strip()
        
        return final_name
