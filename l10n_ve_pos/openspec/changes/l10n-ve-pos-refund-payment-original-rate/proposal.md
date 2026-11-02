# Fix: la línea de PAGO foránea de un reembolso no espejaba al centavo lo que el cliente pagó (l10n_ve_pos)

## Why

El change `l10n-ve-pos-refund-original-rate` ya hizo que las **líneas de
producto** y los **totales** de una orden de reembolso se conviertan a
divisa con la tasa de la venta ORIGINAL, no con la tasa viva de
`pos.config`. Pero las **líneas de pago** quedaron fuera: en la pantalla de
pago de un reembolso, al seleccionar un método `is_foreign_currency`, el
equivalente en moneda principal (`pos.payment.set_foreign_amount` →
`this.amount`, y el prellenado en `addNewPaymentLine`) llamaba directo a
`order.localToForeign()` / `order.foreignToLocal()`, que leen la tasa viva.

Consecuencia (ticket #15114): el monto en Bs de la línea de reembolso no
cuadra con el pago original que el cajero ve en **"ver pagos de origen"**.

Al corregirlo con la tasa **agregada** de la orden
(`get_foreign_total_with_tax / totalDue`) seguía habiendo un desfase de unos
céntimos (p. ej. $45 → 42.556,80 Bs vs 42.556,56 que pagó el cliente),
porque:
1. Esa tasa se deriva de totales ya redondeados por línea, distinta de la
   tasa puntual con la que se grabó el pago foráneo original
   (`amount / foreign_amount`).
2. `get_foreign_total_with_tax()` es **sin signo** mientras `totalDue` es
   **negativo** en reembolsos, así que la proporción salía negativa y
   ensuciaba el multiplicador (`foreign_rate`) y el signo del pago.

El requerimiento de negocio es que el reembolso devuelva **exactamente** lo
que el cliente pagó por esos dólares.

## What Changes

- **`models/pos_order.py`**: nuevo método RPC `get_refund_foreign_rate(order_ids)`
  que devuelve la tasa EXACTA del tender foráneo original:
  `Σ|amount| / Σ|foreign_amount|` sobre los pagos de la(s) orden(es)
  original(es) hechos con un método `is_foreign_currency`. Devuelve `0` si
  no hay tender foráneo que espejar.
- **`static/src/overrides/screens/payment_screen/payment_screen.js`**:
  - `onWillStart` precarga esa tasa (una sola llamada RPC, antes de
    renderizar) para las órdenes de reembolso y la cachea en
    `order.refund_foreign_rate`. No-op silencioso en no-reembolso o error
    (cae al comportamiento anterior).
  - `addNewPaymentLine()`: el prellenado del monto foráneo usa
    `order._convertOrderAmount(localDueBefore)` (que ahora prefiere la tasa
    exacta), no `order.localToForeign`.
- **`static/src/overrides/models/pos_order.js`**:
  - Nuevo `getRefundForeignRate()`: lee la tasa cacheada (`> 0` o `0`).
  - `_convertOrderAmount` / `_convertForeignOrderAmount`: si hay tasa exacta,
    convierten con ella (`local / rate`, `foreign * rate`); si no, caen a la
    proporción por líneas del reembolso; si no, a la tasa viva.
  - `get_effective_foreign_multiplier()`: `1 / tasa_exacta` cuando aplica;
    si no, la proporción en valor absoluto (evita el multiplicador negativo);
    si no, la viva.
- **`static/src/overrides/models/payment_model.js`**:
  - `set_foreign_amount()`: nueva **rama dedicada de reembolso** cuando hay
    tasa exacta. Valora la línea como `|foráneo| × tasa_exacta` (directo,
    espeja el tender del cliente), con el signo del reembolso
    (`foreign_amount` negativo). Solo hace *snap* a la deuda local exacta
    cuando el tender apenas la cubre (dentro de un paso de redondeo foráneo
    convertido a local), para matar la deriva sub-céntimo del prellenado en
    un reembolso total. La lógica de venta (cubre-deuda / parcial) queda
    intacta para todo lo demás.
  - `_recomputeForeignFromLocal()` y `serializeForORM().foreign_rate`:
    enrutados por los helpers refund-aware (tasa exacta cuando aplica).

Todo lo anterior solo se activa cuando `getRefundForeignRate() > 0`, es
decir un reembolso cuya orden original tuvo tender foráneo. En ventas y en
reembolsos sin tender foráneo, el comportamiento anterior no cambia.

## Impact

- **Capability**: `pos-refund-original-rate` (extendida).
- **Módulo**: `l10n_ve_pos`. Frontend
  (`pos_order.js`, `payment_model.js`, `payment_screen.js`) + un método RPC
  de solo lectura en `pos_order.py`. Requiere `-u l10n_ve_pos` (assets +
  método server).
- **Cambio de comportamiento visible**: en un reembolso, la línea de pago
  foránea muestra en Bs **exactamente** lo que el cliente pagó por esos
  dólares (cuadra con "ver pagos de origen"); el `foreign_amount` del pago
  queda con signo de reembolso (negativo) y el `foreign_rate` guardado es
  positivo y consistente. En ventas no cambia nada.
- **Riesgo de despliegue**: bajo — todo detrás de `getRefundForeignRate() > 0`;
  fallback al comportamiento anterior si no hay tasa exacta o falla el RPC.
