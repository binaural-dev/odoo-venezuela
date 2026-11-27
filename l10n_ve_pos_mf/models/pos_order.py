from odoo import models, fields, api, _
from odoo.exceptions import UserError
import pytz

import logging

_logger = logging.getLogger(__name__)


class PosOrderInherit(models.Model):
    _inherit = "pos.order"

    mf_reportz = fields.Char(string="Codigo de reporte Z", default=False, copy=False, readonly=True)
    fiscal_machine = fields.Char(
        string="Serial de Maquina fiscal", default=False, copy=False, readonly=True
    )
    mf_invoice_number = fields.Char(
        string="Sequencia en maquina fiscal", default=False, copy=False, readonly=True
    )
    # Datos para verificar con la máquina una impresión que no confirmó si
    # emitió el documento (TfhkaDriver: `printed: null`). Con valor, el pedido
    # está "por verificar" y no se debe volver a imprimir hasta resolverlo.
    mf_print_verification = fields.Json(
        string="Fiscal print to verify", copy=False, readonly=True
    )

    def get_order_by_uid(self, uid):
        orders = self.env["pos.order"].search([("pos_reference", "ilike", uid)])
        if not orders:
            orders = self.env["pos.order"].search([("uuid", "=", uid)])
        if not orders:
            return []

        result = orders.read([
            "pos_reference",
            "date_order",
            "fiscal_machine",
            "mf_invoice_number",
            "mf_reportz",
        ])

        for values, order in zip(result, orders):
            values["payment_lines"] = [
                {
                    "payment_method_code": payment.payment_method_id.code_fiscal_printer,
                    "payment_method_name": payment.payment_method_id.name,
                    "amount": payment.amount,
                }
                for payment in order.payment_ids
                if payment.payment_method_id
            ]

        return result

    @api.model
    def _load_pos_data_fields(self, config):
        fields_list = list(super()._load_pos_data_fields(config))
        # Si el core devuelve [] significa "todos los campos"; en ese caso
        # no hace falta agregar nada.
        if not fields_list:
            return fields_list
        extra_fields = ["fiscal_machine", "mf_invoice_number", "mf_reportz", "mf_print_verification"]
        for field_name in extra_fields:
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list

    def _prepare_invoice_vals(self):
        self.ensure_one()
        res = super()._prepare_invoice_vals()
        invoice_datetime = fields.Datetime.now()
        if self.session_id.state != "closed" and self.date_order:
            invoice_datetime = self.date_order

        invoice_datetime = fields.Datetime.to_datetime(invoice_datetime)
        if invoice_datetime and invoice_datetime.tzinfo is None:
            invoice_datetime = pytz.UTC.localize(invoice_datetime)

        tz_name = self.user_id.tz or self.env.user.tz or "America/Caracas"
        try:
            timezone = pytz.timezone(tz_name)
        except Exception:
            timezone = pytz.timezone("America/Caracas")

        if invoice_datetime:
            res["invoice_date"] = invoice_datetime.astimezone(timezone).date()

        res["cashbox_id"] = self.config_id.id
        res["mf_serial"] = self.fiscal_machine
        res["mf_invoice_number"] = self.mf_invoice_number
        res["mf_reportz"] = self.mf_reportz
        return res

    def write_mf_invoice_data(self, mf_invoice_number, fiscal_machine, mf_reportz=False):
        """Persiste los datos de impresion fiscal (mf_invoice_number,
        fiscal_machine, mf_reportz) en el pedido y los propaga al
        account.move asociado (si existe).

        Caso de uso: "Imprimir pedido pendiente" desde el TicketScreen. El
        pedido ya fue validado/sincronizado (y su factura contable, si
        aplica, ya se creo) pero la impresion fiscal se omitio o fallo en
        su momento. Al imprimirlo despues, hay que actualizar tanto el
        pedido como la factura contable ya existente con los datos
        fiscales resultantes.

        Se usa sudo() porque estos campos son readonly=True a nivel de
        modelo (solo deben poblarse mediante el flujo de impresion fiscal,
        nunca editados manualmente por el usuario).

        :return: dict con "success" y "account_move_updated" (bool)
        """
        self.ensure_one()
        self._check_company()
        vals = {
            "mf_invoice_number": mf_invoice_number,
            "fiscal_machine": fiscal_machine,
            "mf_reportz": mf_reportz,
        }
        self.sudo().write(vals)

        account_move_updated = False
        if self.account_move:
            self.account_move.sudo().write({
                "mf_invoice_number": mf_invoice_number,
                "mf_serial": fiscal_machine,
                "mf_reportz": mf_reportz,
            })
            account_move_updated = True
        else:
            _logger.warning(
                "write_mf_invoice_data: pos.order %s no tiene account_move asociado, "
                "no se propagaron los datos fiscales a la factura contable.",
                self.id,
            )

        return {
            "success": True,
            "account_move_updated": account_move_updated,
        }

    @api.model
    def mf_set_print_verification(self, uuid, verification):
        """Marca como "por verificar" un pedido ya sincronizado cuya
        impresión (desde "Imprimir pedido pendiente") no confirmó si la
        máquina emitió el documento. Escribe con los permisos del usuario
        del PdV, que puede modificar sus pedidos.

        :param verification: el `verification` del driver
            ({"docType", "before": {...}, "paymentSent", "closeAcked"})
        :return: True si se marcó el pedido
        """
        if not isinstance(verification, dict) or not isinstance(verification.get("before"), dict):
            raise UserError(_("Invalid fiscal print verification data."))
        order = self.search([("uuid", "=", uuid)], limit=1)
        if not order or order.mf_invoice_number:
            return False
        order.mf_print_verification = verification
        return True

    @api.model
    def mf_resolve_print_verification(self, uuid, resolved):
        """Aplica lo que la máquina respondió al verificar un pedido "por
        verificar" (TfhkaDriver.verifyDocument). El PdV lo llama antes de
        imprimir el siguiente documento. Solo cambia pedidos marcados: no
        sirve para poner un número fiscal en cualquier pedido.

        :param resolved: {"printed": bool, "invoiceNumber", "serial", "reportZ"}
        :return: True si ya no queda nada por aplicar (también si el pedido
            no estaba marcado, por ejemplo porque se resolvió desde el
            backend); False si el pedido todavía no está en el servidor (el
            PdV lo reintenta después de sincronizar); o
            {"manual_review": True, "reason"} si el número no puede ser de
            este pedido (los mismos chequeos del asistente): no se aplica, el
            pedido sigue por verificar y queda para el asistente
        """
        if not isinstance(resolved, dict) or not isinstance(resolved.get("printed"), bool):
            raise UserError(_("Invalid fiscal print verification result."))
        # El número viene del driver (texto o entero): solo se aceptan dígitos.
        number = resolved.get("invoiceNumber")
        valid_type = isinstance(number, (str, int)) and not isinstance(number, bool)
        number = str(number).strip() if valid_type else ""
        if resolved["printed"] and not (number.isascii() and number.isdigit()):
            raise UserError(_("A printed fiscal document needs its fiscal number."))
        order = self.search([("uuid", "=", uuid)], limit=1)
        if not order:
            return False
        if not order.mf_print_verification:
            return True
        serial = resolved.get("serial") or False
        reportz = resolved.get("reportZ") or False
        kept_number = order.mf_invoice_number
        if resolved["printed"] and not kept_number:
            # El navegador arma `resolved`: se valida como lo que escribe a
            # mano el gerente, para no darle el número de otro documento.
            problem = order._mf_check_fiscal_number(number, serial, order.mf_print_verification)
            if problem:
                order._mf_log_rejected_print_verification(
                    order.mf_print_verification, number, serial, problem
                )
                return {"manual_review": True, "reason": problem}
            order.write_mf_invoice_data(number, serial, reportz)
        order._mf_log_print_verification(
            order.mf_print_verification,
            resolved["printed"],
            number,
            serial,
            reportz,
            kept_number=kept_number,
        )
        order.mf_print_verification = False
        return True

    def _mf_log_print_verification(
        self,
        verification,
        printed,
        number=False,
        serial=False,
        reportz=False,
        manual=False,
        kept_number=False,
    ):
        """Deja en el chatter quién resolvió un pedido por verificar, cómo y
        con qué foto de la máquina: la foto se pierde al quitar la marca, y
        "no emitido" es justo lo que habilita volver a imprimir. Tarea 85447.

        :param kept_number: número fiscal que el pedido ya tenía y conserva
        """
        self.ensure_one()
        before = (verification or {}).get("before") or {}
        if kept_number and printed and self._mf_same_fiscal_number(kept_number, number):
            kept_number = False
        if kept_number and printed:
            result = _(
                "the fiscal printer reported number %(number)s, but the order already had the "
                "fiscal number %(kept)s and keeps it",
                number=number,
                kept=kept_number,
            )
        elif kept_number:
            result = _(
                "the fiscal printer did not print it, and the order keeps the fiscal number "
                "%(kept)s it already had",
                kept=kept_number,
            )
        elif printed:
            result = _(
                "the fiscal printer printed it as number %(number)s (fiscal printer %(serial)s, "
                "Z report %(reportz)s)",
                number=number,
                serial=serial or "-",
                reportz=reportz or "-",
            )
        else:
            result = _("the fiscal printer did not print it, so the order is pending to invoice")
        if manual:
            body = _(
                "Fiscal print resolved manually: %(result)s. Reading of the fiscal printer "
                "before the print: last number %(number)s, fiscal printer %(serial)s, Z counter "
                "%(closures)s.",
                result=result,
                number=before.get("number", "-"),
                serial=before.get("serial") or "-",
                closures=before.get("dailyClosureCounter", "-"),
            )
        else:
            body = _(
                "Fiscal print verified by the PoS with the fiscal printer: %(result)s. Reading of "
                "the fiscal printer before the print: last number %(number)s, fiscal printer "
                "%(serial)s, Z counter %(closures)s.",
                result=result,
                number=before.get("number", "-"),
                serial=before.get("serial") or "-",
                closures=before.get("dailyClosureCounter", "-"),
            )
        # sudo: el cajero escribe el pedido con sus permisos, pero publicar
        # en el chatter lee la compañía (alias de correo). Autor: quien resolvió.
        self.sudo().message_post(body=body, author_id=self.env.user.partner_id.id)

    @api.model
    def _mf_same_fiscal_number(self, first, second):
        """Mismo número fiscal por su valor: "00000505" es el 505."""
        first, second = str(first or "").strip(), str(second or "").strip()
        if first.isascii() and first.isdigit() and second.isascii() and second.isdigit():
            return int(first) == int(second)
        return first == second

    def _mf_fiscal_document_type(self):
        """Tipo de documento fiscal del pedido: la máquina numera aparte las
        facturas y las notas de crédito. Tarea 85447."""
        self.ensure_one()
        is_refund = self.amount_total < 0 or any(self.lines.mapped("refunded_orderline_id"))
        return "credit_note" if is_refund else "invoice"

    def _mf_fiscal_number_owner(self, number, serial, doc_type):
        """Otro pedido o factura que ya tiene ese número fiscal en esa máquina,
        para el mismo tipo de documento (facturas, notas de crédito y de débito
        llevan contadores separados). Compara el valor del número: "00000101"
        es el 101. Tarea 85447.

        :return: el nombre del documento, o False si el número está libre
        """
        self.ensure_one()
        value = int(number)
        pattern = f"%{value}"
        # sudo: el número es único por máquina en toda la base, y el gerente
        # puede no ver los pedidos ni los asientos de otras cajas.

        def same_number(other):
            other = (other or "").strip()
            return other.isascii() and other.isdigit() and int(other) == value

        orders = self.sudo().search(
            [
                ("id", "!=", self.id),
                ("fiscal_machine", "=", serial),
                ("mf_invoice_number", "=like", pattern),
            ]
        )
        for other in orders:
            if same_number(other.mf_invoice_number) and other._mf_fiscal_document_type() == doc_type:
                return other.display_name
        moves = self.env["account.move"].sudo().search(
            [
                ("id", "not in", self.account_move.ids),
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("mf_serial", "=", serial),
                ("mf_invoice_number", "=like", pattern),
            ]
        )
        for move in moves:
            if same_number(move.mf_invoice_number) and move._mf_fiscal_document_type() == doc_type:
                return move.display_name
        return False

    def _mf_check_fiscal_number(self, number, serial, verification):
        """Motivo por el que un número fiscal no puede ser el del documento
        por verificar de este pedido, o False si puede serlo. Lo usan el
        asistente y la resolución del PdV (`mf_resolve_print_verification`).
        Tarea 85447.

        - El documento solo pudo salir en la máquina de la foto: un error de
          tipeo en el serial también esquivaría el chequeo de duplicados.
        - Con un número posterior al que tenía la máquina antes de imprimirlo.
        - Que no sea de otro pedido o factura de esa máquina y ese tipo de
          documento.

        :param number: número fiscal, solo dígitos
        :param serial: serial de la máquina; vacío si el driver no lo leyó
            (se compara entonces con la máquina de la foto)
        :param verification: el `mf_print_verification` del pedido
        :return: el motivo (texto para el usuario) o False
        """
        self.ensure_one()
        verification = verification or {}
        before = verification.get("before") or {}
        expected_serial = (before.get("serial") or "").strip()
        serial = (serial or "").strip()
        if expected_serial and serial and serial != expected_serial:
            return _(
                "The document could only be printed on the fiscal printer %(expected)s, "
                "the one connected when it was printed.",
                expected=expected_serial,
            )
        last_number = before.get("number")
        if isinstance(last_number, int) and int(number) <= last_number:
            return _(
                "The fiscal number must be greater than %(last)s, the last number of the "
                "fiscal printer before printing this order.",
                last=last_number,
            )
        # El número esperado es el siguiente al de la foto, y si la máquina
        # emitió algo más en el medio ese número puede ser de otro documento.
        machine = serial or expected_serial
        if machine:
            doc_type = verification.get("docType") or self._mf_fiscal_document_type()
            owner = self._mf_fiscal_number_owner(number, machine, doc_type)
            if owner:
                return _(
                    "The fiscal number %(number)s of the fiscal printer %(serial)s already "
                    "belongs to %(owner)s. Check on the fiscal printer which document "
                    "belongs to this order.",
                    number=number,
                    serial=machine,
                    owner=owner,
                )
        return False

    def _mf_log_rejected_print_verification(self, verification, number, serial, reason):
        """Deja en el chatter que el PdV verificó la impresión con la máquina
        pero el número no se aplicó (ver `_mf_check_fiscal_number`): el pedido
        sigue por verificar para el asistente. Tarea 85447."""
        self.ensure_one()
        before = (verification or {}).get("before") or {}
        body = _(
            "Fiscal print verified by the PoS with the fiscal printer, but not applied: the "
            "fiscal printer reported number %(number)s (fiscal printer %(serial)s). %(reason)s "
            "The order stays to verify until a PoS manager resolves it from the order. Reading "
            "of the fiscal printer before the print: last number %(last)s, fiscal printer "
            "%(before_serial)s, Z counter %(closures)s.",
            number=number,
            serial=serial or "-",
            reason=reason,
            last=before.get("number", "-"),
            before_serial=before.get("serial") or "-",
            closures=before.get("dailyClosureCounter", "-"),
        )
        # sudo: como en `_mf_log_print_verification`. Autor: quien verificó.
        self.sudo().message_post(body=body, author_id=self.env.user.partner_id.id)

    def action_mf_resolve_print_verification(self):
        """Abre el asistente para resolver a mano un pedido por verificar."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Resolve fiscal print"),
            "res_model": "pos.order.mf.verification.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_order_id": self.id},
        }

    @api.model
    def validate_order_dry_run(self, orders):
        """Valida contablemente una orden sin persistirla.

        Ejecuta sync_from_ui dentro de un SAVEPOINT y siempre hace
        ROLLBACK. Si la validacion falla (impuestos mal configurados,
        diario faltante, etc.) la excepcion se propaga al POS ANTES de
        imprimir en la maquina fiscal, evitando documentos fiscales
        emitidos para ordenes que luego no se pueden contabilizar.

        En Odoo 19 las ordenes ya no consumen una secuencia del
        pos.config (la referencia se deriva del uuid), por lo que no hay
        secuencias que restaurar tras el rollback.

        :param orders: lista de dicts serializados (serializeForORM)
        :return: True si la orden es contablemente valida
        """
        self.env.cr.execute("SAVEPOINT pos_dry_run")

        try:
            # Agregamos generate_pdf=False para evitar la generación de PDF durante
            # el dry-run, que causa el error de wkhtmltopdf no instalado
            self.with_context(generate_pdf=False).sync_from_ui(orders)
        except Exception:
            self.env.cr.execute("ROLLBACK TO SAVEPOINT pos_dry_run")
            raise

        self.env.cr.execute("ROLLBACK TO SAVEPOINT pos_dry_run")

        return True

    def _generate_pos_order_invoice(self):
        """Override para evitar generación de PDF cuando está configurado.
        
        Si la caja tiene mf_skip_invoice_pdf activado, generamos la factura
        sin crear el PDF (evita dependencia de wkhtmltopdf).

        NOTA: No se puede usar super().with_context(...).method() porque
        with_context retorna un recordset de la misma clase hija, y al
        llamar .method() sobre él, Odoo resuelve de nuevo este override,
        causando recursión infinita.
        """
        if self.config_id.mf_skip_invoice_pdf:
            _logger.info("MF:: Generando factura sin PDF para orden %s", self.id)
            ctx_self = self.with_context(generate_pdf=False)
            return super(PosOrderInherit, ctx_self)._generate_pos_order_invoice()
        return super()._generate_pos_order_invoice()
