from odoo import models, fields, api, _
from odoo.exceptions import UserError

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
        extra_fields = ["fiscal_machine", "mf_invoice_number", "mf_reportz"]
        for field_name in extra_fields:
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list

    def _prepare_invoice_vals(self):
        self.ensure_one()
        res = super()._prepare_invoice_vals()
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
            self.sync_from_ui(orders)
        except Exception:
            self.env.cr.execute("ROLLBACK TO SAVEPOINT pos_dry_run")
            raise

        self.env.cr.execute("ROLLBACK TO SAVEPOINT pos_dry_run")

        return True
