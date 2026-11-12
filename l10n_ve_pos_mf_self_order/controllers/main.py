import logging

from odoo import _, http
from odoo.exceptions import UserError

from odoo.addons.pos_self_order.controllers.orders import PosSelfOrderController

_logger = logging.getLogger(__name__)


class L10nVePosMfSelfOrderController(PosSelfOrderController):
    """Rutas públicas de la máquina fiscal para el Kiosko.

    En la caja, la persistencia del número fiscal y el cierre con Reporte Z se
    hacen con ``orm.call`` autenticados (``PrintPendingOrderButton`` y
    ``ClosePosPopup.closeSessionAndPrintZ`` de ``l10n_ve_pos_mf``). El Kiosko
    corre como público (``auth="public"`` + ``access_token``) y no puede hacer
    ``orm.call`` arbitrario, así que se exponen rutas públicas dedicadas que
    validan el ``access_token`` (reusando ``_verify_pos_config``) y que lo que
    tocan pertenezca a la caja antes de delegar en los mismos métodos
    server-side que usa la caja.
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
            return {"success": False, "error": _("Order not found for this POS")}
        # Guard de integridad: NO re-numerar una orden con un número fiscal
        # DISTINTO al que ya tiene. Sobrescribir un correlativo SENIAT ya
        # emitido con otro lo corrompe. Reenviar el MISMO número (reintento de
        # persistencia tras un timeout, §3.4) es un no-op inofensivo y se
        # permite, para que ese reintento sea idempotente. Un primer intento
        # legítimo llega con el campo vacío, así que tampoco se bloquea. (No se
        # comprueba el estado `posted` del account.move: escribir el número
        # fiscal sobre una factura ya posteada ES el flujo normal en VE.)
        if order.mf_invoice_number and order.mf_invoice_number != mf_invoice_number:
            return {"success": False, "error": _("This order already has a fiscal number")}
        return order.write_mf_invoice_data(
            mf_invoice_number, fiscal_machine, mf_reportz or False
        )

    # -- Cierre de sesión con Reporte Z (ticket 16406) -----------------------
    # Espejo de `ClosePosPopup.closeSessionAndPrintZ` de la caja: el cliente
    # pregunta por las órdenes pendientes, imprime la Z en la máquina (Web
    # Serial, solo el navegador del Kiosko la ve), la sincroniza con Odoo y
    # cierra la sesión. Cada paso es una ruta para que el orden y los cortes
    # sean los mismos que en la caja.

    def _l10n_ve_kiosk_pending_close_orders(self, pos_config):
        """Órdenes de la sesión abierta de la caja sin número fiscal.

        Mismo criterio que la caja (``ClosePosPopup._getUnfiscalizedOrders``):
        cualquier orden de la sesión sin ``mf_invoice_number`` que no esté
        cancelada, salvo los borradores. En el Kiosko un borrador es un carrito
        que nadie pagó, y el cierre nativo
        (``pos.config.action_close_kiosk_session``) los borra. Incluye las órdenes
        pagadas con la factura contable diferida (``is_invoiced`` falso).
        """
        session = pos_config.sudo().current_session_id
        if not session:
            return pos_config.env["pos.order"].sudo()
        return (
            pos_config.env["pos.order"]
            .sudo()
            .search(
                [
                    ("session_id", "=", session.id),
                    ("state", "not in", ("draft", "cancel")),
                    ("mf_invoice_number", "=", False),
                ],
                order="id asc",
            )
        )

    def _l10n_ve_kiosk_orders_payload(self, orders):
        return [
            {
                "id": order.id,
                "name": order.name,
                "pos_reference": order.pos_reference,
                "is_invoiced": order.is_invoiced,
            }
            for order in orders
        ]

    @http.route(
        "/l10n_ve_pos_mf_self_order/kiosk/close_session/check",
        auth="public",
        type="jsonrpc",
        website=True,
    )
    def l10n_ve_kiosk_close_session_check(self, access_token):
        """Órdenes que impiden imprimir la Z y cerrar la sesión del Kiosko."""
        pos_config = self._verify_pos_config(access_token)
        orders = self._l10n_ve_kiosk_pending_close_orders(pos_config)
        return {"pending_orders": self._l10n_ve_kiosk_orders_payload(orders)}

    @http.route(
        "/l10n_ve_pos_mf_self_order/kiosk/report_z",
        auth="public",
        type="jsonrpc",
        website=True,
    )
    def l10n_ve_kiosk_report_z(self, access_token, value):
        """Sincroniza con Odoo el Reporte Z que el Kiosko acaba de imprimir.

        Recibe el mismo ``value`` que arma la caja tras leer S1
        (``{"valid": True, "data": {"_registeredMachineNumber",
        "_dailyClosureCounter"}}``) y delega en los mismos métodos:
        ``account.move.report_z`` (marca el Z en las facturas y órdenes de la
        máquina que no lo tienen) y ``pos.session.set_report_z``.

        Con ``sudo``: el usuario del Kiosko no suele tener permisos contables.
        Por eso las facturas solo se marcan si la caja ya imprimió con esa
        máquina (alguna de sus órdenes tiene ese ``fiscal_machine``): con el
        token del Kiosko no se puede poner un Z en las facturas de otra
        máquina.
        """
        pos_config = self._verify_pos_config(access_token)
        value = value if isinstance(value, dict) else {}
        data = value.get("data") if isinstance(value.get("data"), dict) else {}
        serial = data.get("_registeredMachineNumber")
        counter = data.get("_dailyClosureCounter")
        if (
            not value.get("valid")
            or not serial
            or not isinstance(serial, str)
            or not isinstance(counter, int)
            or isinstance(counter, bool)
        ):
            return {"success": False, "error": _("Invalid Z report data")}

        config_sudo = pos_config.sudo()
        session = config_sudo.current_session_id
        env = pos_config.env
        try:
            with env.cr.savepoint():
                used_by_box = env["pos.order"].sudo().search_count(
                    [
                        ("config_id", "=", pos_config.id),
                        ("fiscal_machine", "=", serial),
                    ],
                    limit=1,
                )
                if used_by_box:
                    env["account.move"].sudo().report_z(serial, value)
                session.set_report_z(value)
        except Exception as error:  # noqa: BLE001 — devolver el motivo al panel
            _logger.exception(
                "Kiosk report_z falló para la caja %s (serial %s)", pos_config.id, serial
            )
            return {"success": False, "error": str(error)}
        return {"success": True, "report_z": session.report_z}

    @http.route(
        "/l10n_ve_pos_mf_self_order/kiosk/close_session",
        auth="public",
        type="jsonrpc",
        website=True,
    )
    def l10n_ve_kiosk_close_session(self, access_token):
        """Cierra la sesión del Kiosko con el cierre nativo, tras la Z.

        Vuelve a revisar las órdenes pendientes (la regla vale aunque alguien
        llame la ruta sin pasar por el panel) y delega en
        ``pos.config.action_close_kiosk_session``, el mismo cierre que el botón
        Cerrar del backend.

        Si el cierre falla, el error sale de la ruta y el framework revierte
        toda la petición: la sesión queda abierta y se cierra desde el backend.
        No se usa un ``savepoint``: cuando el asiento de cierre no cuadra, el
        cierre nativo hace ``cr.rollback()`` y devuelve el asistente de
        diferencias en vez de cerrar, lo que invalida cualquier ``savepoint``.
        Ese caso se detecta porque la sesión no quedó cerrada.
        """
        pos_config = self._verify_pos_config(access_token)
        pending = self._l10n_ve_kiosk_pending_close_orders(pos_config)
        if pending:
            return {
                "success": False,
                "error": _(
                    "There are %s order(s) without a fiscal invoice in this session.",
                    len(pending),
                ),
                "pending_orders": self._l10n_ve_kiosk_orders_payload(pending),
            }
        config_sudo = pos_config.sudo()
        session = config_sudo.current_session_id
        config_sudo.action_close_kiosk_session()
        if session.state != "closed":
            _logger.warning(
                "Kiosk close_session: la sesión %s de la caja %s no quedó cerrada",
                session.id,
                pos_config.id,
            )
            raise UserError(
                _(
                    "The session could not be closed from the Kiosk (the closing entry needs "
                    "review). Close it from the backend."
                )
            )
        return {"success": True, "session_id": session.id}
