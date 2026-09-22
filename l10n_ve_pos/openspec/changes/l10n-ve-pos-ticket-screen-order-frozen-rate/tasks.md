# Tasks

## 1. Tasa congelada por orden finalizada (frontend)

- [x] 1.1 `pos_order.js`: `_frozenOrderMultiplier()` lee
      `this.foreign_currency_rate` (`> 0`, si no `0`)
- [x] 1.2 `pos_order.js`: `_isFrozenRateOrder()` = `this.finalized` y hay
      tasa congelada; `_frozenLocalToForeign()` convierte main→foreign con
      esa tasa redondeando con `foreign_currency`
- [x] 1.3 `pos_order.js`: `get_foreign_total_with_tax/without_tax/tax`
      usan la tasa congelada para ventas finalizadas (branch después del
      de reembolso, antes del `localToForeign` vivo)
- [x] 1.4 `pos_order.js`: `get_display_rate()` para orden finalizada
      muestra la tasa que sus montos usan (venta = congelada; reembolso =
      derivada de totales), con fallback al comportamiento vivo previo
- [x] 1.5 `pos_order_line.js`: `_localToForeignMoney()` usa la tasa
      congelada de la orden para líneas de una venta finalizada

## 2. Verificación manual (navegador, 2doce)

- [ ] 2.1 Abrir en el TicketScreen una venta con divisa de otro día: la
      tasa mostrada y el total/impuesto en divisa reflejan la tasa de la
      venta, no la de hoy
- [ ] 2.2 El monto en divisa por línea cuadra con el total en divisa de la
      orden
- [ ] 2.3 Reimprimir Documento Fiscal usa esos mismos valores
- [ ] 2.4 Venta de mostrador en vivo, pantalla de pago e impresión MF sin
      cambios (siguen a la tasa viva)
- [ ] 2.5 Nota de crédito vista en el TicketScreen sigue con la tasa del
      original (sin regresión del change previo)

## 3. OpenSpec

- [x] 3.1 `openspec validate --changes`
