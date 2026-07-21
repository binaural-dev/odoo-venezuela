# Tasks

## 1. Limpieza de código muerto

- [x] 1.1 Eliminar `static/src/overrides/components/orderline/orderline.js`
      (verificado por grep: ningún método del patch se invocaba desde XML
      ni JS en todo el módulo)

## 2. Tasa original en reembolsos

- [x] 2.1 `pos_order_line.js`: `_refundOriginalRate()` — lee
      `refunded_orderline_id.order_id.foreign_currency_rate`
- [x] 2.2 `_get_raw_foreign_unit_price()` usa la tasa congelada cuando
      aplica
- [x] 2.3 `_localToForeignMoney()` usa la tasa congelada cuando aplica
      (afecta a todos los `get_foreign_price_*`/`get_all_foreign_prices`
      vía `_conv`)

## 2.1 Hotfix HI.1 — total de la orden (encontrado al verificar en navegador)

- [x] 2.1.1 Confirmado en vivo (orden 8016 / INV/2026/0028): el total
      mostrado en pantalla de pago seguía usando tasa viva pese al fix de
      2.1-2.3, porque viene de `pos_order.js::get_foreign_total_with_tax()`
      (convierte el TOTAL agregado), no de la suma de líneas
- [x] 2.1.2 `pos_order.js`: `_hasRefundLines()` + `_sumForeignLines()`;
      `get_foreign_total_with_tax/without_tax/tax` suman por línea cuando
      hay líneas de reembolso
- [x] 2.1.3 `pos_order.js`: `_convertOrderAmount()` aplicado a
      `get_foreign_due()`/`get_foreign_change()`

## 3. Badge (G)/(E)

- [x] 3.1 `get_aliquot_type()` reimplementado en `pos_order_line.js` sin
      depender de `this.pos.taxes_by_id`
- [x] 3.2 `orderline.xml`: `line.aliquot_type` → `line.get_aliquot_type()`

## 4. Verificación manual (confirmada en navegador, 2026-07-20)

- [ ] 4.1 Confirmar que el badge "(G)"/"(E)" aparece junto al nombre del
      producto en el PdV, para productos gravados y exentos (no
      re-confirmado explícitamente por el usuario en esta sesión — el foco
      de la prueba fue la tasa)
- [x] 4.2 Vendida orden 37 (INV/2026/0028) con tasa 0,001428112596396;
      tasa viva al momento de probar el reembolso: 0,001356424930
- [x] 4.3 Reembolso de la orden 37: pantalla de pago mostró $20,31,
      calculado con la tasa original (0,001428112596396), no con la tasa
      viva (que hubiera dado $19,29). Diagnosticado en vivo con logging
      temporal `[RVDBG]` (ya retirado) — confirmó `_refundOriginalRate()`
      devolviendo la tasa correcta y `get_foreign_total_with_tax()` usando
      el camino SUM
- [x] 4.3.1 Verificado que $20,31 coincide exactamente con
      `pos_order.foreign_amount_total` (20.31) y
      `account_move.foreign_total_billed` (20.31) de la orden/factura
      original (BD `pos`, contenedor `proj_db`) — no con el cálculo manual
      aproximado del usuario ($20,32)
- [x] 4.3.2 El "$20,32" que el usuario vio en el asiento contable
      (vista de líneas del `account.move`) se explicó: es la suma de
      TODAS las líneas del asiento, incluida una línea de costo de
      mercancía/inventario ($0,01) ajena a la deuda del cliente. Las
      líneas relevantes al cliente (venta + IVA) suman $20,31, igual que
      el reembolso — no hay discrepancia real
- [ ] 4.4 Confirmar que una venta normal (no reembolso) sigue mostrando
      el monto en USD con la tasa viva de `pos.config` (sin regresión) —
      no probado explícitamente, pero la rama de código no cambia para
      órdenes sin `refunded_orderline_id`
- [ ] 4.5 Probar un reembolso de una orden vieja sin
      `foreign_currency_rate` poblado (dato legado): confirmar que cae al
      comportamiento anterior (tasa viva) sin romperse

## 5. OpenSpec

- [x] 5.1 `openspec validate --changes`
