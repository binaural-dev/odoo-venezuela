import logging
import time
from collections import defaultdict, deque
from threading import Lock

from odoo import _, http
from odoo.exceptions import UserError

from odoo.addons.pos_self_order.controllers.orders import PosSelfOrderController

_logger = logging.getLogger(__name__)

# --- Anti-abuso de las rutas públicas de identificación ------------------
# Las rutas ``identify``/``identify_create``/``set_phone`` corren con
# ``sudo()`` a propósito: el Kiosko puede abrirse con un usuario deliberadamente
# capado (que solo ve el Kiosko) y aun así debe poder buscar/registrar al
# cliente. Como no hay record rules que frenen una enumeración de cédulas
# (``res.partner`` no está scopeado por compañía en este código), el freno es
# un rate-limit por ``access_token`` (el token del dispositivo, uno por caja).
#
# El límite está calibrado para NO tocar el uso real: una fila de clientes,
# cada uno tecleando su cédula una o dos veces al finalizar la orden anterior,
# genera un puñado de llamadas por minuto. Solo muerde cuando alguien scripea
# cientos/miles de consultas contra la ruta. Es en memoria del worker (ventana
# deslizante): suficiente para una tienda física; el tope es por-worker, no
# global (si algún día se quiere estricto entre varios workers, migrar a algo
# persistido).
_RATE_LIMIT_WINDOW = 60  # segundos de la ventana
_RATE_LIMIT_MAX = 60  # máximo de llamadas de identificación por ventana y token
_rate_lock = Lock()
_rate_buckets = defaultdict(deque)

# Cédula (V/E) y RIF (J/G) son numéricos; P (pasaporte)/C se dejan libres.
_NUMERIC_PREFIXES = ("V", "E", "J", "G")


def _ve_within_rate_limit(access_token):
    """True si la petición cabe dentro del rate-limit; False si hay que frenar.

    Ventana deslizante por ``access_token`` en memoria del worker. Registra el
    instante actual solo cuando acepta, para no penalizar peticiones ya
    rechazadas.
    """
    now = time.time()
    cutoff = now - _RATE_LIMIT_WINDOW
    with _rate_lock:
        bucket = _rate_buckets[access_token]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= _RATE_LIMIT_MAX:
            return False
        bucket.append(now)
        return True


def _ve_vat_format_error(prefix_vat, vat):
    """Devuelve el mensaje de error de formato, o ``None`` si es válido.

    Valida en el servidor lo mismo que el cliente (``identification_page.js``):
    la cédula (V/E) y el RIF (J/G) son solo dígitos; pasaporte (P) y C quedan
    libres.
    """
    vat = (vat or "").strip()
    if not vat:
        return _("Enter the ID number.")
    if prefix_vat in _NUMERIC_PREFIXES and not vat.isdigit():
        return _("The ID number must contain only digits.")
    return None


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
    ``access_token`` and run with ``sudo()`` (the Kiosk may run under a
    locked-down user), returning only the fields the Kiosk needs (id, name)
    plus the ``vat``/``prefix_vat`` the customer just typed to identify
    themselves — the cédula is not a leak (it is their own, already entered)
    and downstream payment integrations (e.g. Megasoft,
    ``binaural_megasoft_self_order``) read it from the order's partner instead
    of asking for it again.

    ``identify`` never returns the partner's ``phone``: since the route is
    public, returning it would let anyone iterate cédulas (sequential in VE)
    and harvest phone numbers. It returns a ``has_phone`` flag instead, so the
    Kiosk knows whether to ask the customer to complete a missing phone
    (``set_phone``, fill-only — never overwrites an existing one). All three
    routes are rate-limited per ``access_token`` (see module top).
    """

    def _ve_find_partner(self, pos_config, prefix_vat, vat):
        """Búsqueda determinista del partner por cédula/RIF (compartida por las
        tres rutas). ``sudo()`` a propósito (ver docstring de la clase). El
        ``order`` desempata duplicados de forma estable: primero compañías
        (``is_company``), luego el ``id`` más bajo.
        """
        return (
            pos_config.env["res.partner"]
            .sudo()
            .search(
                [("prefix_vat", "=", prefix_vat), ("vat", "=", vat)],
                order="is_company desc, id asc",
                limit=1,
            )
        )

    @http.route(
        "/l10n_ve_pos_self_order/kiosk/identify",
        auth="public",
        type="jsonrpc",
        website=True,
    )
    def l10n_ve_kiosk_identify(self, access_token, prefix_vat, vat):
        pos_config = self._verify_pos_config(access_token)
        if not _ve_within_rate_limit(access_token):
            return {"res.partner": [], "error": _("Too many attempts. Please wait a moment.")}
        # Same match criterion as res.partner.check_duplicate_vat's domain
        # (prefix_vat + vat), without a company_id filter — res.partner is not
        # scoped by company in this codebase.
        partner = self._ve_find_partner(pos_config, prefix_vat, vat)
        return {
            # NO ``phone`` here: the public route must not hand out phone
            # numbers to whoever probes cédulas. ``has_phone`` tells the Kiosk
            # whether to ask the customer to complete it.
            "res.partner": partner.read(["id", "name", "vat", "prefix_vat"], load=False),
            "has_phone": bool(partner.phone),
            "error": False,
        }

    @http.route(
        "/l10n_ve_pos_self_order/kiosk/identify/create",
        auth="public",
        type="jsonrpc",
        website=True,
    )
    def l10n_ve_kiosk_identify_create(self, access_token, prefix_vat, vat, name, phone):
        pos_config = self._verify_pos_config(access_token)
        if not _ve_within_rate_limit(access_token):
            return {"res.partner": [], "error": _("Too many attempts. Please wait a moment.")}

        format_error = _ve_vat_format_error(prefix_vat, vat)
        if format_error:
            return {"res.partner": [], "error": format_error}

        # Dedup: si la cédula ya existe, NO crear un duplicado. Devolver el
        # existente y —solo si le falta— rellenarle el teléfono (fill-only,
        # nunca sobrescribe uno que ya tenía).
        partner_model = pos_config.env["res.partner"].sudo()
        partner = self._ve_find_partner(pos_config, prefix_vat, vat)
        if partner:
            if phone and not partner.phone:
                partner.phone = phone
            return {
                "res.partner": partner.read(["id", "name", "vat", "prefix_vat"], load=False),
                "error": False,
            }

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
            "res.partner": partner.read(["id", "name", "vat", "prefix_vat"], load=False),
            "error": False,
        }

    @http.route(
        "/l10n_ve_pos_self_order/kiosk/identify/set_phone",
        auth="public",
        type="jsonrpc",
        website=True,
    )
    def l10n_ve_kiosk_identify_set_phone(self, access_token, prefix_vat, vat, phone):
        """Rellena el teléfono de un cliente EXISTENTE que no lo tenía.

        El Kiosko llama a esta ruta cuando ``identify`` devolvió el cliente pero
        con ``has_phone`` falso. Se vuelve a localizar al partner por su
        cédula/RIF (no se confía en un ``id`` arbitrario del cliente público) y
        se rellena el teléfono **solo si estaba vacío**: una ruta pública nunca
        debe poder cambiar el teléfono que el cliente ya tenía registrado.
        """
        pos_config = self._verify_pos_config(access_token)
        if not _ve_within_rate_limit(access_token):
            return {"res.partner": [], "error": _("Too many attempts. Please wait a moment.")}

        phone = (phone or "").strip()
        partner = self._ve_find_partner(pos_config, prefix_vat, vat)
        if not partner:
            return {"res.partner": [], "error": _("Customer not found.")}
        # Fill-only: nunca sobrescribir un teléfono ya existente.
        if phone and not partner.phone:
            partner.phone = phone
        return {
            "res.partner": partner.read(["id", "name", "vat", "prefix_vat"], load=False),
            "error": False,
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
        #
        # Tope DURO al `limit` (independiente del valor recibido): esta ruta es
        # pública, así que un `limit` enorme no debe poder volcar todo el
        # histórico de la caja de una sola llamada.
        try:
            limit = min(int(limit or 50), 200)
        except (TypeError, ValueError):
            limit = 50
        orders = (
            pos_config.env["pos.order"]
            .sudo()
            .search(
                [
                    ("config_id", "=", pos_config.id),
                    ("state", "in", ["paid", "done", "invoiced"]),
                ],
                order="id desc",
                limit=limit,
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
