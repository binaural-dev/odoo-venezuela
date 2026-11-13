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
            PdV lo reintenta después de sincronizar)
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
        if resolved["printed"] and not order.mf_invoice_number:
            order.write_mf_invoice_data(
                number,
                resolved.get("serial") or False,
                resolved.get("reportZ") or False,
            )
        order.mf_print_verification = False
        return True

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
