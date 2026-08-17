from odoo import api, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def _load_pos_self_data_fields(self, config):
        """Expone los datos fiscales de la orden al cliente del Kiosko.

        El Kiosko imprime la factura fiscal en LOCAL (Web Serial) y guarda el
        número devuelto por la máquina en la orden en memoria. Para que ese
        número viaje al servidor con la orden (``serializeForORM`` solo incluye
        campos que el esquema del cliente conoce) y ``_prepare_invoice_vals`` lo
        estampe en el ``account.move`` al sincronizar, el esquema del cliente
        del Kiosko debe conocer estos campos. ``l10n_ve_pos_mf`` ya los expone
        en el loader de caja; aquí se replica para el Kiosko.
        """
        fields_list = list(super()._load_pos_self_data_fields(config))
        for field_name in ("mf_invoice_number", "fiscal_machine", "mf_reportz"):
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list

    def _send_payment_result(self, payment_result):
        """Incluir ``pos.payment`` en el evento del bus ``PAYMENT_STATUS``.

        El método del core solo emite ``pos.order`` + ``pos.order.line`` (no los
        pagos), así que en el cliente del Kiosko ``order.payment_ids`` llega
        VACÍO al confirmar. La impresión fiscal (que se dispara en
        ``SelfOrder.confirmationPage``) necesita el método de pago para leer su
        ``code_fiscal_printer`` y armar las líneas de pago del comprobante.

        Se reemplaza el método (no hay hook para ampliar el payload) añadiendo
        ``pos.payment`` — leído con sus campos self-data — al ``data`` del bus,
        para que ``connectNewData`` conecte los pagos a la orden en el cliente.
        """
        self.ensure_one()
        self.config_id._notify(
            "PAYMENT_STATUS",
            {
                "payment_result": payment_result,
                "data": {
                    "pos.order": self.read(
                        self._load_pos_self_data_fields(self.config_id), load=False
                    ),
                    "pos.order.line": self.lines.read(
                        self.lines._load_pos_self_data_fields(self.config_id), load=False
                    ),
                    "pos.payment": self.payment_ids.read(
                        self.payment_ids._load_pos_self_data_fields(self.config_id),
                        load=False,
                    ),
                },
            },
        )
        if payment_result == "Success":
            self._send_self_order_receipt()
            self._send_order()
