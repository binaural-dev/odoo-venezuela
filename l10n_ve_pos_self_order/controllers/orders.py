import logging

from odoo import _, http
from odoo.exceptions import UserError

from odoo.addons.pos_self_order.controllers.orders import PosSelfOrderController

_logger = logging.getLogger(__name__)


class L10nVePosSelfOrderController(PosSelfOrderController):
    """Kiosk customer identification by cédula/RIF for the Venezuelan Self
    Order flow.

    ``l10n_ve_pos`` forces ``to_invoice=True`` on every POS order (SENIAT
    requirement), so the Kiosk must identify the customer before the order is
    built instead of billing the generic consumer. These two public routes are
    called by ``IdentificationPage`` at the very start of the order:

    * ``identify`` looks up an existing partner by ``prefix_vat`` + ``vat``.
    * ``identify_create`` creates a new partner when the cédula is unknown.

    Both reuse the core ``_verify_pos_config`` helper to validate the
    ``access_token`` and run under the pos.config's company/user context, and
    return only the fields the Kiosk needs (id, name, phone) plus the
    ``vat``/``prefix_vat`` the customer just typed to identify themselves — the
    cédula is not a leak (it is their own, already entered) and downstream
    payment integrations (e.g. Megasoft, ``binaural_megasoft_self_order``) read
    it from the order's partner instead of asking for it again.
    """

    @http.route(
        "/l10n_ve_pos_self_order/kiosk/identify",
        auth="public",
        type="jsonrpc",
        website=True,
    )
    def l10n_ve_kiosk_identify(self, access_token, prefix_vat, vat):
        pos_config = self._verify_pos_config(access_token)
        # Same match criterion as res.partner.check_duplicate_vat's domain
        # (prefix_vat + vat), without a company_id filter — res.partner is not
        # scoped by company in this codebase.
        partner = (
            pos_config.env["res.partner"]
            .sudo()
            .search([("prefix_vat", "=", prefix_vat), ("vat", "=", vat)], limit=1)
        )
        return {
            "res.partner": partner.read(
                ["id", "name", "phone", "vat", "prefix_vat"], load=False
            ),
        }

    @http.route(
        "/l10n_ve_pos_self_order/kiosk/identify/create",
        auth="public",
        type="jsonrpc",
        website=True,
    )
    def l10n_ve_kiosk_identify_create(self, access_token, prefix_vat, vat, name, phone):
        pos_config = self._verify_pos_config(access_token)
        partner_model = pos_config.env["res.partner"].sudo()

        vals = {
            "name": name,
            "phone": phone,
            "prefix_vat": prefix_vat,
            "vat": vat,
        }
        # Preload the company address defaults exactly like the reduced partner
        # form of the regular POS box does, via l10n_ve_pos's default_get gated
        # by the l10n_ve_pos_partner_defaults context flag. No new address logic.
        default_fields = list(partner_model._POS_COMPANY_DEFAULT_FIELDS)
        address_defaults = partner_model.with_context(
            l10n_ve_pos_partner_defaults=True
        ).default_get(default_fields)
        vals.update(address_defaults)

        # Create under the pos.config's company context (same env as the
        # lookup) so res.partner's default company_id resolves to the box's
        # company, mirroring how validate_partner creates with sudo().
        partner = partner_model.create(vals)
        return {
            "res.partner": partner.read(
                ["id", "name", "phone", "vat", "prefix_vat"], load=False
            ),
        }

    @http.route(
        "/l10n_ve_pos_self_order/kiosk/create_invoice",
        auth="public",
        type="jsonrpc",
        website=True,
    )
    def l10n_ve_kiosk_create_invoice(self, access_token, order_id):
        """Crea la factura de una orden del Kiosko que quedó pendiente de facturar.

        Contraparte pública del Kiosko para recuperar una orden pagada cuya
        facturación falló al finalizar (ver ``pos.order._process_saved_order`` en
        este módulo). Valida el ``access_token`` (``_verify_pos_config``) y que la
        orden pertenezca a la caja, igual que el endpoint fiscal
        (``write_mf_invoice_data``). Idempotente: si la orden ya tiene
        ``account_move``, no crea una segunda; devuelve el estado actual.

        A diferencia de la finalización automática, aquí NO se pone el flag
        ``kiosk_defer_invoice``: si la facturación vuelve a fallar, la excepción se
        captura y se devuelve el motivo real para que el panel lo muestre, sin
        tragar el error en silencio.
        """
        pos_config = self._verify_pos_config(access_token)
        order = pos_config.env["pos.order"].sudo().browse(int(order_id))
        if not order.exists() or order.config_id.id != pos_config.id:
            return {"success": False, "error": _("Order not found for this POS")}
        if order.account_move:
            return {
                "success": True,
                "invoice_id": order.account_move.id,
                "already_invoiced": True,
            }
        # Facturar dentro de un savepoint: si la creación de la factura falla —o
        # se crea pero NO llega a publicarse (`_post`)— se revierte TODO para no
        # dejar un `account.move` en borrador colgado de la orden. Un borrador así
        # bloquearía el cierre de la sesión (chequeo NATIVO
        # `pos.session._check_invoices_are_posted`: "invoices are not posted") y
        # dejaría la orden en un estado a medias. Con el rollback, la orden vuelve
        # a quedar pagada/pendiente de facturar (recuperable de nuevo), sin basura.
        try:
            with pos_config.env.cr.savepoint():
                order.action_pos_order_invoice()
                if not order.account_move or order.account_move.state != "posted":
                    raise UserError(_("The invoice was not posted."))
        except Exception as error:  # noqa: BLE001 — devolver el motivo al panel
            _logger.exception(
                "Kiosk create_invoice falló para la orden %s", order.id
            )
            # El savepoint revirtió la BD (incl. el borrador y el enlace
            # account_move); limpiar la caché para que la orden refleje su estado
            # real (sin factura).
            order.invalidate_recordset()
            return {"success": False, "error": str(error)}
        return {"success": True, "invoice_id": order.account_move.id}

    @http.route(
        "/l10n_ve_pos_self_order/kiosk/session_orders",
        auth="public",
        type="jsonrpc",
        website=True,
    )
    def l10n_ve_kiosk_session_orders(self, access_token, limit=50):
        """Órdenes recientes de la caja, para el panel de órdenes del Kiosko.

        Persistencia real: el panel NO depende de lo que quede en memoria del
        cliente (que se pierde al iniciar una orden nueva o recargar). Devuelve
        ``pos.order``/``line``/``payment``/``partner`` en el mismo formato que
        consume ``connectNewData`` en el cliente, así el panel las lista y —si el
        módulo de máquina fiscal está instalado— el builder fiscal client-side las
        usa igual (líneas, impuestos, pago) para imprimir o reimprimir la copia.

        Datos genéricos: los campos fiscales (``mf_invoice_number``…) NO se piden
        aquí; se añaden solos cuando ``l10n_ve_pos_mf_self_order`` está instalado,
        porque extiende ``pos.order._load_pos_self_data_fields``. Así el panel de
        recuperación de factura funciona en un Kiosko sin máquina fiscal.
        """
        pos_config = self._verify_pos_config(access_token)
        # Últimas órdenes de ESTA caja (cualquier sesión), no solo la sesión
        # abierta: así el panel muestra también las de turnos anteriores para
        # recuperar facturas pendientes (o reimprimir copias con MF). Acotado por
        # límite.
        orders = (
            pos_config.env["pos.order"]
            .sudo()
            .search(
                [
                    ("config_id", "=", pos_config.id),
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
