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
