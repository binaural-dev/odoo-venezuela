# Tasks

## 1. Diagnóstico (hecho — solo lectura)

- [x] 1.1 Punto de fallo: el Kiosko factura de forma atómica con la creación de
      la orden (controlador `process_order` + `_process_saved_order(False)`, esta
      última invocada por `_payment_request_from_kiosk` en el flujo Megasoft). Un
      fallo de facturación hace rollback de todo el request → se pierde orden +
      pago pese al cobro en VPOS.
- [x] 1.2 El ciclo de vida de la orden del Kiosko lo gobierna
      `l10n_ve_pos_self_order` (fuerza `to_invoice` en `_check_pos_order`,
      totales foráneos, cola `kiosk_sync_queue.js`) → es el módulo dueño de la
      resiliencia de facturación.
- [x] 1.3 La respuesta del VPOS se descarta en `payment_page.js` tras validar
      `codRespuesta === "00"`. Ni la caja ni el Kiosko persisten
      `numeroAutorizacion/Referencia/Lote/Tarjeta/...`. El `payment_status="done"`
      que "bloquea" la línea en la caja es runtime, no BD.
- [x] 1.4 Confirmado en el manual VPOS (MAET-VPOSW-00) que `accion:"tarjeta"`
      devuelve el JSON con auth/referencia/lote/tarjeta/banco/voucher.

## 2. Backend resiliente — seam de facturación (`l10n_ve_pos_self_order`)

- [x] 2.1 Seam confirmado (core Odoo 19, `point_of_sale/models/pos_order.py`):
      `_process_saved_order` hace `action_pos_order_paid` + `_create_order_picking`
      + `_compute_total_cost_in_real_time` y luego `self._generate_pos_order_invoice()`.
      Se eligió la opción (a): flag de contexto `kiosk_defer_invoice` +
      savepoint dentro de `_generate_pos_order_invoice` (menos drift que
      reproducir el tramo).
- [x] 2.2 `models/pos_order.py`: override de `_process_saved_order` (gateado a
      `self_ordering_mode=='kiosk'` + `to_invoice` + no draft/cancel) que llama a
      super con `kiosk_defer_invoice=True`; y override de
      `_generate_pos_order_invoice` que, con ese flag, envuelve `super()` en
      `with self.env.cr.savepoint()`; ante excepción `_logger.exception(...)` +
      `invalidate_recordset()` (limpiar `state='done'` revertido) y deja la orden
      `paid`/`to_invoice`/sin `account_move`. Sin flag → comportamiento del core.
- [x] 2.3 Idempotencia verificada: `_create_order_picking` guarda
      `if self.picking_ids: return`; pago por `already_paid`; factura por
      `account_move`. El reintento (reapertura a 'draft') no duplica.
- [~] 2.4 Descartado el `computed`: el menú de backend usa un DOMINIO directo
      (`config_id.self_ordering_mode='kiosk' & state='paid' & to_invoice &
      account_move=False`), sin campo extra.

## 3. Endpoint de facturación diferida + menú de backend (`l10n_ve_pos_self_order`)

- [x] 3.1 Ruta pública `/l10n_ve_pos_self_order/kiosk/create_invoice`
      (`controllers/orders.py`): `_verify_pos_config` + `order.config_id ==
      pos_config`; si ya hay `account_move`, devuelve estado (idempotente); si no,
      `action_pos_order_invoice()` dentro de un `savepoint` + exige que quede
      `posted`; ante fallo revierte (NO deja borrador colgado) y devuelve
      `{success:false, error}`. CLAVE: un `account.move` en borrador bloquea el
      cierre de sesión (chequeo NATIVO `pos.session._check_invoices_are_posted`:
      "invoices are not posted"). Misma garantía "publicada o nada" en
      `_generate_pos_order_invoice` (finalización).
- [x] 3.2 `views/pos_order_views.xml`: `act_window`
      `action_kiosk_pending_invoice_orders` con el dominio de pendientes. Se
      reutiliza el form estándar de `pos.order` (ya trae el botón **Invoice** →
      `action_pos_order_invoice`), así que no hace falta vista custom ni server-action.
- [x] 3.3 Menú `menu_kiosk_pending_invoice_orders` bajo
      `point_of_sale.menu_point_of_sale` (grupo `group_pos_manager`). Añadido a
      `data` del manifest.

## 4. Cola de reintento (`l10n_ve_pos_self_order/kiosk_sync_queue.js`)

- [x] 4.1 Documentado en el docstring: los rechazos de facturación ya NO llegan a
      `failed` (el RPC responde OK y la orden queda pendiente en el servidor);
      `failed` queda para rechazos fatales del registro completo.

## 5. Persistir la verificación Megasoft *(impacto: `binaural_megasoft_self_order`)*

- [x] 5.1 `models/pos_payment.py` (NUEVO): campos `megasoft_vpos_response` (Text) +
      `megasoft_auth/reference/lote/card/card_type/bank/resp_code` (Char),
      `string`/`help` en español. Añadido al `models/__init__.py`.
- [x] 5.2 `payment_page.js`: guarda `data` del VPOS en `this._megasoftVposData` y
      lo pone en `order.megasoft_vpos_response` (JSON) ANTES de serializar → viaja
      online y en el payload encolado offline. (Transporte por la ORDEN, no un
      kwarg extra: el core `pos_self_order_kiosk_payment` no acepta kwargs nuevos.)
- [x] 5.3 `pos.order.megasoft_vpos_response` (Text) como canal de transporte +
      expuesto en `pos.order._load_pos_self_data_fields`. `_payment_request_from_kiosk`
      parsea ese JSON (`_megasoft_payment_vals_from_order`) y estampa raw +
      subconjunto en el `add_payment` vals. NO cambia la lógica de facturación.
- [x] 5.4 Campos `megasoft_*` expuestos al cliente SIN override del loader: el
      core `pos.payment` NO define `_load_pos_data_fields` → hereda `[]` y
      `read([])` = TODOS los campos, que ya incluye los `megasoft_*` (reales). Un
      override con lista explícita ROMPÍA la carga (quitaba `payment_method_id` →
      "Método: —" y "sin code_fiscal_printer"); se eliminó (prueba navegador).
- [x] 5.5 CORREGIDO bug del Kiosko (mismo ta 78767, distinto del recovery):
      foreign_debit/credit en cero en las facturas del Kiosko. Causa: la factura
      copia `foreign_price` de `pos.order.line` (l10n_ve_pos
      `_get_invoice_lines_values`), que en la CAJA lo calcula el frontend por línea
      pero el Kiosko dejaba NULL. Fix en `recompute_prices` (este módulo): setear
      `line.foreign_price = config._convert(line.price_unit, currency_id,
      foreign_currency_id)` para cada línea, misma conversión que
      `foreign_amount_total`. Verificado contra caja (line 724: 2.5). NOTA: solo
      arregla órdenes NUEVAS; las ya creadas necesitan data-fix (recompute).

## 6. Fiscal + panel de recuperación *(impacto: `l10n_ve_pos_mf_self_order`)*

- [x] 6.1 `self_order_fiscal.js` (`confirmationPage`): guarda `order.is_invoiced`
      (ya llega al cliente vía el loader del core) — no auto-imprimir si la factura
      contable está pendiente. El overlay solo se activa cuando sí se imprime.
- [x] 6.2 `kiosk_fiscal_orders_dialog`: `orderStatus()` de tres niveles
      (_pending_invoice_ · _pending_fiscal_ · _complete_) reflejado en la lista
      (badges) y el detalle.
- [x] 6.3 Sección "Pago verificado" en el detalle (`selectedPayment`): método +
      autorización/referencia/lote/tarjeta/banco de la `pos.payment`.
- [x] 6.4 Acción por estado: "Crear factura" (`onCreateInvoice` → `createKioskInvoice`
      → endpoint 3.1, recarga) → "Imprimir factura fiscal" → "Reimprimir copia".
      Mensajes/motivos visibles.
- [x] 6.5 Recuperación SOLO en modo debug (decisión del usuario): se descartó el
      botón visible en la raíz del Kiosko. El panel se abre desde el menú Debug MF
      (`?debug=1`) → "Órdenes fiscales" (`MfDebugDialog.onOpenOrders`). La vía de
      contabilidad es el menú de backend (§3).
- [x] 6.6 `session_orders` ya lee `pos.payment`; los campos `megasoft_*` fluyen
      solos por `_load_pos_self_data_fields` (sin cambio en el controlador). Las
      `paid` sin `account_move` ya entran por `state='paid'`.

## 7. Tests (Python; el usuario los corre — ver
   [[feedback-no-comandos-pesados-sin-permiso]])

- [ ] 7.1 Facturación falla (mock que lanza en el generador) → la orden queda
      `state='paid'`, `to_invoice=True`, `account_move=False`, con su `pos.payment`
      (pago NO duplicado); `_send_payment_result` se llamó.
- [ ] 7.2 Facturación OK → estado final normal (con `account_move`), idéntico a hoy.
- [ ] 7.3 Reintento de `create_invoice` sobre una orden ya facturada → no crea
      segunda factura (idempotente).
- [ ] 7.4 `pos.payment` persiste los campos Megasoft desde `megasoft_result`.
- [ ] 7.5 `_load_pos_self_data_fields` de `pos.payment` incluye los campos nuevos.

## 8. Verificación manual (navegador, por el usuario)

- [ ] 8.0 QUITAR antes del commit final: palanca de prueba en
      `pos.order._generate_pos_order_invoice` (System Parameter
      `kiosk.force_invoice_error` ∈ 1/true/yes/on → UserError forzado). Solo para
      validar la recuperación; no afecta caja ni el endpoint `create_invoice`.
- [ ] 8.1 Forzar rechazo de factura (`kiosk.force_invoice_error=1`, o una fecha de
      bloqueo contable) tras aprobar pago → la orden se crea y queda pendiente; el
      cliente ve confirmación; NO se imprime fiscal.
- [ ] 8.2 Con órdenes pendientes, el botón de recuperación aparece SIN debug;
      abre el panel con el estado y el pago verificado.
- [ ] 8.3 Corregir la causa → "Crear factura" factura la orden → "Imprimir
      factura fiscal" imprime y persiste el número.
- [ ] 8.4 Menú de backend lista las pendientes y permite facturarlas.
- [ ] 8.5 Regresión: camino feliz (factura OK) idéntico a hoy; caja normal intacta.

## 9. OpenSpec

- [x] 9.1 `openspec validate --type change l10n-ve-pos-self-order-kiosk-invoice-recovery
      --strict` → válido.
- [x] 9.2 Proposal + design + spec delta + tasks escritos.
