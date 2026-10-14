# Tasks

## 1. Tasa exacta del tender foráneo original (server)

- [x] 1.1 `pos_order.py`: `get_refund_foreign_rate(order_ids)` —
      `Σ|amount| / Σ|foreign_amount|` de los pagos `is_foreign_currency` de
      la(s) orden(es) original(es); `0` si no hay tender foráneo

## 2. Prefetch y cacheo (frontend)

- [x] 2.1 `payment_screen.js`: `onWillStart` → `_prefetchRefundForeignRate()`
      llama al RPC para reembolsos y cachea `order.refund_foreign_rate`
- [x] 2.2 `pos_order.js`: `getRefundForeignRate()` lee la tasa cacheada
- [x] 2.3 `pos_order.js`: `_convertOrderAmount` / `_convertForeignOrderAmount`
      prefieren la tasa exacta (`local/rate`, `foreign*rate`)
- [x] 2.4 `pos_order.js`: `get_effective_foreign_multiplier` = `1/exacta`
      (positivo), con `Math.abs` de la proporción como respaldo

## 3. Rama dedicada de reembolso en la línea de pago

- [x] 3.1 `payment_model.js`: `set_foreign_amount()` — cuando hay tasa exacta,
      valora `|foráneo| × tasa` (directo) con signo de reembolso; snap a la
      deuda solo dentro de un paso de redondeo foráneo (tolerancia
      `tasa × rounding`)
- [x] 3.2 `payment_screen.js`: prellenado vía `_convertOrderAmount`
- [x] 3.3 `payment_model.js`: `_recomputeForeignFromLocal` y
      `serializeForORM.foreign_rate` enrutados por los helpers refund-aware

## 4. Tests unitarios (hoot)

- [x] 4.1 `tests/unit/utils.js`: `makeOrderStub` acepta `refundExactRate` y
      expone `getRefundForeignRate`, `roundLocalMoney`, `roundForeignMoney`
- [x] 4.2 `tests/unit/payment_model.test.js`: cubre-deuda hace snap; sobrepago
      y parcial convierten directo a la tasa exacta; el signo tecleado no
      importa; snap solo dentro de la tolerancia; respaldo sin tasa exacta;
      `_recomputeForeignFromLocal` usa la tasa exacta
- [x] 4.3 Los tests de venta normal siguen pasando (tasa exacta = 0)

## 5. Verificación manual (navegador, 2doce)

- [ ] 5.1 Reembolso de una orden con pago foráneo: teclear el mismo monto en
      $ y confirmar que el Bs coincide EXACTO con "ver pagos de origen"
- [ ] 5.2 Confirmar signo negativo del `foreign_amount` y `foreign_rate`
      positivo en el pago guardado
- [ ] 5.3 Venta normal sin cambios

## 6. OpenSpec

- [x] 6.1 `openspec validate --changes`
