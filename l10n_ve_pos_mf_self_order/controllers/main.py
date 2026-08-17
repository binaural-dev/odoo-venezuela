from odoo import http

from odoo.addons.pos_self_order.controllers.orders import PosSelfOrderController


class L10nVePosMfSelfOrderController(PosSelfOrderController):
    """Persistencia del número fiscal para el Kiosko (frontend PÚBLICO).

    En la caja, tras imprimir una orden ya registrada, se guarda el número
    fiscal con ``pos.order.write_mf_invoice_data`` vía un ``orm.call``
    autenticado (``PrintPendingOrderButton``). El Kiosko corre como público
    (``auth="public"`` + ``access_token``) y no puede hacer ``orm.call``
    arbitrario, así que se expone una ruta pública dedicada que valida el
    ``access_token`` (reusando ``_verify_pos_config``) y que la orden pertenezca
    a la caja antes de delegar en el mismo método server-side
    (``write_mf_invoice_data``, que persiste en la orden y propaga al
    ``account.move``).
    """

    @http.route(
        "/l10n_ve_pos_mf_self_order/kiosk/write_mf_invoice_data",
        auth="public",
        type="jsonrpc",
        website=True,
    )
    def l10n_ve_kiosk_write_mf_invoice_data(
        self, access_token, order_id, mf_invoice_number, fiscal_machine, mf_reportz=False
    ):
        pos_config = self._verify_pos_config(access_token)
        order = pos_config.env["pos.order"].sudo().browse(int(order_id))
        # La orden debe existir y pertenecer a la caja del access_token: el
        # Kiosko público no puede escribir el número fiscal de cualquier orden.
        if not order.exists() or order.config_id.id != pos_config.id:
            return {"success": False, "error": "Orden no encontrada para esta caja"}
        return order.write_mf_invoice_data(
            mf_invoice_number, fiscal_machine, mf_reportz or False
        )

    @http.route(
        "/l10n_ve_pos_mf_self_order/kiosk/session_orders",
        auth="public",
        type="jsonrpc",
        website=True,
    )
    def l10n_ve_kiosk_session_orders(self, access_token, limit=50):
        """Órdenes de la sesión abierta de la caja, para el panel de órdenes
        fiscales del Kiosko (persistencia real: no dependen de lo que haya en
        memoria del cliente, que se pierde al iniciar una orden nueva o recargar).

        Devuelve pos.order/line/payment/partner en el mismo formato que consume
        ``connectNewData`` en el cliente, así el panel las lista y el builder
        fiscal client-side las usa igual (líneas, impuestos, pago) para imprimir
        o reimprimir la copia.
        """
        pos_config = self._verify_pos_config(access_token)
        session = pos_config.current_session_id
        if not session:
            return {}
        orders = (
            pos_config.env["pos.order"]
            .sudo()
            .search(
                [
                    ("session_id", "=", session.id),
                    ("state", "in", ["paid", "done", "invoiced"]),
                ],
                order="id desc",
                limit=int(limit) or 50,
            )
        )
        if not orders:
            return {}
        env = pos_config.env
        return {
            "pos.order": env["pos.order"]._load_pos_self_data_read(orders, pos_config),
            "pos.order.line": env["pos.order.line"]._load_pos_self_data_read(
                orders.lines, pos_config
            ),
            "pos.payment": env["pos.payment"]._load_pos_self_data_read(
                orders.payment_ids, pos_config
            ),
            "res.partner": env["res.partner"]._load_pos_self_data_read(
                orders.partner_id, pos_config
            ),
        }
