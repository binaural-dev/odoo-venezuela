import logging

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def _check_pos_order(self, pos_config, order, device_type, table=None):
        """Force ``to_invoice=True`` on every Kiosk order.

        ``l10n_ve_pos`` requires every POS sale to emit a fiscal invoice
        (SENIAT), and enforces it on the cashier by patching the JS
        ``PosOrder`` in the ``point_of_sale._assets_pos`` bundle
        (``static/src/overrides/models/pos_order.js`` — ``setup``/
        ``serializeForORM``). The Kiosk/Self-Order app ships a *different*
        asset bundle (``pos_self_order.assets``) that never loads that patch,
        so the client sends no ``to_invoice`` and the core ``_check_pos_order``
        copies that missing value straight through — the Kiosk order ends up
        NOT invoiced.

        Force it server-side here, the one method that builds the Kiosk order
        vals. Gated to ``self_ordering_mode == 'kiosk'`` (same scope as the
        cédula identification flow, which is what guarantees the order carries
        a real ``partner_id`` to invoice): the ``mobile``/QR flow has no such
        guarantee and must not be forced to invoice against the generic
        consumer.
        """
        vals = super()._check_pos_order(pos_config, order, device_type, table)
        if pos_config.self_ordering_mode == "kiosk":
            vals["to_invoice"] = True
        return vals

    def recompute_prices(self):
        """``recompute_prices`` (pos_self_order) recalculates ``amount_total``
        authoritatively from the real catalog after the Kiosk/Self-Order
        controller creates an order, to defend against a tampered client
        payload. It never touches the Venezuelan foreign-currency fields,
        so ``l10n_ve_pos``'s provisional value (from
        ``_complete_values_from_session``, based on the client-submitted
        total) goes stale the moment this recompute corrects the total.

        Mirror the same ``pos.config._convert``/``_get_pos_conversion_rate``
        contract used everywhere else in ``l10n_ve_pos`` to keep the foreign
        total in sync with the now-authoritative local total.
        """
        super().recompute_prices()
        config = self.config_id
        self.foreign_amount_total = config._convert(
            self.amount_total, self.currency_id, config.foreign_currency_id
        )
        self.foreign_currency_rate = config._get_pos_conversion_rate(
            self.currency_id, config.foreign_currency_id
        )
        # Cada línea necesita su ``foreign_price`` (precio unitario en moneda
        # foránea). La factura lo copia TAL CUAL de ``pos.order.line.foreign_price``
        # (``l10n_ve_pos._get_invoice_lines_values``), y de ahí ``l10n_ve_accountant``
        # deriva foreign_subtotal/foreign_debit/foreign_credit. En la CAJA lo
        # calcula el frontend del PoS por línea (``setUnitPrice`` →
        # ``localToForeign``); el bundle del Kiosko NO carga ese patch, así que las
        # líneas llegaban sin ``foreign_price`` (NULL) y la factura del Kiosko
        # salía con foreign_debit/credit en cero. Se calcula aquí con la MISMA
        # conversión que ``foreign_amount_total`` (``config._convert``, que
        # redondea con la moneda foránea), para que cuadre con la caja.
        for line in self.lines:
            line.foreign_price = config._convert(
                line.price_unit, self.currency_id, config.foreign_currency_id
            )

    def _process_saved_order(self, draft):
        """Kiosk: hacer la facturación resiliente — nunca perder una orden pagada
        por un fallo al facturar.

        El ``_process_saved_order`` del core marca la orden pagada + picking +
        costo y **luego factura, todo en la MISMA transacción**
        (``point_of_sale/models/pos_order.py``). Si la facturación lanza
        (secuencia SENIAT, diario, impuesto, dato del partner...), el request HTTP
        completo hace rollback y la orden del Kiosko se **pierde** aunque la
        tarjeta ya se cobró en el VPOS de Megasoft.

        Para las órdenes del Kiosko dejamos que el core corra tal cual, pero
        marcando el contexto ``kiosk_defer_invoice`` para que
        ``_generate_pos_order_invoice`` (abajo) aísle SOLO la generación de la
        factura en un ``savepoint``. Si falla, la orden queda ``paid`` +
        ``to_invoice`` sin ``account_move`` (pendiente de facturar), recuperable
        desde el panel del Kiosko / el menú de backend, en vez de desaparecer.

        Gateado a ``self_ordering_mode == 'kiosk'`` para no alterar la caja ni el
        ``mobile``/QR. Agnóstico al método de pago: cubre Megasoft y cualquier
        terminal futuro que finalice por esta vía.
        """
        if (
            not draft
            and self.config_id.self_ordering_mode == "kiosk"
            and self.to_invoice
            and self.state != "cancel"
        ):
            return super(
                PosOrder, self.with_context(kiosk_defer_invoice=True)
            )._process_saved_order(draft)
        return super()._process_saved_order(draft)

    def _generate_pos_order_invoice(self):
        """Aísla la generación de la factura del Kiosko en un ``savepoint``.

        Solo actúa cuando ``_process_saved_order`` pidió diferir
        (``kiosk_defer_invoice`` en el contexto): así la finalización automática
        del Kiosko no pierde la orden si falla la factura, pero la creación de
        factura **explícita** (endpoint de recuperación / menú de backend, que NO
        ponen el flag) sigue lanzando el error para que el operador vea la causa.
        """
        if not self.env.context.get("kiosk_defer_invoice"):
            return super()._generate_pos_order_invoice()
        try:
            with self.env.cr.savepoint():
                invoice = super()._generate_pos_order_invoice()
                # Exigir que la factura quede PUBLICADA: si `_create_invoice`
                # crea el borrador pero `_post` no lo publica (sin lanzar), un
                # `account.move` en borrador colgado bloquearía el cierre de la
                # sesión (chequeo nativo `pos.session._check_invoices_are_posted`).
                # Tratarlo como fallo → el savepoint revierte y la orden queda
                # pagada/pendiente de facturar, sin borrador.
                if not self.account_move or self.account_move.state != "posted":
                    raise UserError(_("The Kiosk invoice was not posted."))
                return invoice
        except Exception:  # noqa: BLE001 — conservar la orden pagada, diferir la factura
            _logger.exception(
                "Kiosk order %s: facturación diferida; la orden queda pagada, "
                "pendiente de facturar.",
                self.id,
            )
            # El savepoint revirtió la BD (incluido el ``state='done'`` que
            # ``_generate_pos_order_invoice`` fija de primero); limpiar la caché
            # ORM para que quien lea la orden vea el estado real (``paid``).
            self.invalidate_recordset()
            return self.env["account.move"]
