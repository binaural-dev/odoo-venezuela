# Tasks

## 1. Diagnóstico (hecho en esta sesión — solo lectura)

- [x] 1.1 Confirmar que `to_invoice` en el Kiosko llega del payload del cliente
      sin forzarse server-side (`pos_self_order.pos.order._check_pos_order`
      línea 230: `'to_invoice': order.get('to_invoice')`), y que el patch JS
      que lo fuerza en la caja (`l10n_ve_pos/.../models/pos_order.js:23-25`)
      vive en el bundle del cajero, no en el del Kiosko
- [x] 1.2 Confirmar que la finalización de Megasoft
      (`_payment_request_from_kiosk`) solo llamaba `action_pos_order_paid()`
      (pone `state='paid'`, no factura) y nunca `_process_saved_order` /
      `_generate_pos_order_invoice`
- [x] 1.3 Localizar el patrón correcto de cierre de orden de autopedido desde
      el servidor: `pos_online_payment/models/payment_transaction.py:63-64`
      (`pos_order._process_saved_order(False)`)
- [x] 1.4 Confirmar que el cálculo foráneo del pago (`foreign_amount`/
      `foreign_rate` en `add_payment` → `foreign_debit`/`foreign_credit` en
      `_create_payment_moves`) ya estaba bien y solo faltaba disparar la
      factura

## 2. Implementación

- [x] 2.1 `l10n_ve_pos_self_order/models/pos_order.py`: override de
      `_check_pos_order` que fuerza `to_invoice=True` cuando
      `self_ordering_mode == 'kiosk'`. Añadir import de `api`
- [x] 2.2 `binaural_megasoft_self_order/models/pos_payment_method.py`: en
      `_payment_request_from_kiosk`, sustituir `action_pos_order_paid()` por la
      finalización completa (`_process_saved_order(False)`), con guardas de
      idempotencia por `account_move` (factura) además del `already_paid`
      existente (pago), y restauración de estado en el reintento tras factura

## 3. Tests

> Pendiente: no ejecutados en este pase (convención del repo — el usuario los
> corre). Escritos abajo.

- [x] 3.1 `l10n_ve_pos_self_order/tests/test_kiosk_to_invoice.py`:
      `_check_pos_order` fuerza `to_invoice=True` en kiosko (payload `False`,
      ausente, o ya `True`); y NO lo fuerza en `mobile`/`consultation`/
      `nothing` (respetando un `True` que sí mande el cliente)
- [x] 3.2 `binaural_megasoft_self_order/tests/test_kiosk_payment_invoicing.py`
      (wiring, con spy sobre `_process_saved_order`): finaliza vía
      `_process_saved_order(False)` con el pago foráneo correcto; los 4 métodos
      tarjeta-presente (PDV/BioPago/Transf/P2C) finalizan; se emite
      `_send_payment_result('Success')`; un método NO-Megasoft delega en super
      (no factura); guardas de estado (`paid` no-`draft` no re-finaliza)
- [x] 3.3 `binaural_megasoft_self_order/tests/test_kiosk_payment_invoicing.py`
      (idempotencia): reintento antes de facturar no duplica pago; reintento
      tras factura (`account_move` ya existe) no re-factura y restaura estado
- [x] 3.4 `binaural_megasoft_self_order/tests/test_kiosk_invoice_accounting.py`
      (integración end-to-end, SIN mocks): `_payment_request_from_kiosk` real →
      factura posteada al cliente + `manually_set_rate`/`foreign_rate` en la
      factura. Dos niveles:
      - PROPAGACIÓN (valor foráneo fijo): el monto que lleva la orden llega
        intacto a `foreign_debit`/`foreign_credit` del asiento de pago.
      - CÁLCULO (tasa sembrada): `recompute_prices` COMPUTA
        `foreign_amount_total = _convert(amount_total, VES, USD)` (no lo copia
        del payload), se verifica el número esperado (≈ total/tasa) y que ESE
        valor calculado es el que termina en `foreign_debit`/`foreign_credit`
- [ ] 3.5 Correr la suite en el contenedor `proj` — pendiente (el usuario la
      corre). El test de integración (3.4) es sensible al entorno; ajustar si
      la cadena de posteo lo requiere en la BD concreta

## 4. Verificación manual (navegador, por el usuario)

- [ ] 4.1 Kiosko con `megasoft_kiosk_test_mode` (simulación, sin VPOS):
      completar una orden → confirmar en backoffice que se generó factura
      posteada a nombre del cliente identificado
- [ ] 4.2 Revisar el asiento de la factura y el de pago: `foreign_debit`/
      `foreign_credit` cuadrados con el total foráneo (VES) de la orden
- [ ] 4.3 Regresión: caja normal (cajero) sigue facturando igual — el fix no la
      toca
- [ ] 4.4 Regresión: modo `mobile`/QR de mesas no cambia (no se fuerza factura)

## 5. OpenSpec

- [x] 5.1 `openspec change validate l10n-ve-pos-self-order-kiosk-invoicing`
      → válido
