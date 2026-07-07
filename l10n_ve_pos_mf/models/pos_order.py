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
    def _order_fields(self, ui_order):
        res = super()._order_fields(ui_order)
        res["fiscal_machine"] = ui_order.get("fiscal_machine", False)
        res["mf_invoice_number"] = ui_order.get("mf_invoice_number", False)
        res["mf_reportz"] = ui_order.get("mf_reportz", False)
        return res

    def _export_for_ui(self, order):
        res = super()._export_for_ui(order)
        res["fiscal_machine"] = order.fiscal_machine
        res["mf_invoice_number"] = order.mf_invoice_number
        res["mf_reportz"] = order.mf_reportz
        return res

    @api.model
    def _load_pos_data_fields(self, config):
        fields = list(super()._load_pos_data_fields(config))
        extra_fields = ["fiscal_machine", "mf_invoice_number", "mf_reportz"]
        for field_name in extra_fields:
            if field_name not in fields:
                fields.append(field_name)
        return fields

    def _prepare_invoice_vals(self):
        self.ensure_one()
        res = super()._prepare_invoice_vals()
        res["cashbox_id"] = self.config_id.id
        res["mf_serial"] = self.fiscal_machine
        res["mf_invoice_number"] = self.mf_invoice_number
        res["mf_reportz"] = self.mf_reportz
        # DEPRECATED: res["iot_mf"] = self.config_id.iface_fiscal_data_module.id
        # Ya no usamos IoT Box, la máquina fiscal se conecta vía Web Serial API
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
        nunca editados manualmente por el usuario) y un write() normal
        desde el ORM del frontend los ignora silenciosamente.

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
        session_id = False
        if orders and isinstance(orders, list):
            session_id = orders[0].get('data', {}).get('pos_session_id')

        sequence = False
        last_next_number = False

        if session_id:
            session = self.env['pos.session'].browse(session_id)
            
            sequence = session.config_id.sequence_id

        if sequence:
            last_next_number = sequence.number_next_actual

        self.env.cr.execute('SAVEPOINT pos_dry_run')
        
        try:
            self.create_from_ui(orders)
        except Exception as e:
            self.env.cr.execute('ROLLBACK TO SAVEPOINT pos_dry_run')
            if sequence and last_next_number:
                sequence.sudo().write({'number_next_actual': last_next_number})
            raise e
                
        self.env.cr.execute('ROLLBACK TO SAVEPOINT pos_dry_run')
        if sequence and last_next_number:
            sequence.sudo().write({'number_next_actual': last_next_number})
                
        return True
