# Fix: los montos foráneos de un reembolso se guardaban positivos (l10n_ve_pos)

## Why

Tarea 83148, hallazgo H1 de la prueba e2e del PdV multimoneda (01-oct-2026).
En un reembolso `pos.payment.amount` y `pos.order.amount_total` son negativos,
pero el PdV mandaba `foreign_amount` y `foreign_amount_total` **positivos**.
`binaural_pos_close` y los cruces suman `foreign_amount` tal cual, así que el
reembolso contaba como efectivo que entra:

- cierre con faltante falso (el doble del reembolso; 23,20 $ en la prueba);
- cruces inflados, extractos y 1122003 descuadrados en alterno;
- si el neto de un método de efectivo foráneo era un reembolso, el cruce salía
  con debe positivo y `amount_currency` negativo y el cierre reventaba
  (`account_move_line_check_amount_currency_balance_sign`).

Causa: en Odoo 19 el core da el `priceIncl`/`priceExcl` de cada línea
multiplicado por `order.orderSign` (−1 en un reembolso), una magnitud positiva
para mostrar, mientras `totalDue` sigue negativo. `_sumForeignLines` sumaba esas
magnitudes, el total foráneo del reembolso salía positivo y las proporciones
`total foráneo / totalDue` de `_convertOrderAmount` y
`_convertForeignOrderAmount` negativas, lo que invertía el signo del
`foreign_amount` de los pagos (métodos foráneos vía `addNewPaymentLine`,
métodos locales vía `_recomputeForeignFromLocal`). Solo se salvaban los
reembolsos con tasa exacta del tender foráneo original
(`l10n-ve-pos-refund-payment-original-rate`). Ese change ya había visto la
proporción negativa y la tapó con `Math.abs` en
`get_effective_foreign_multiplier`, sin corregir el total.

## What Changes

- **`static/src/overrides/models/pos_order.js`**:
  - `_sumForeignLines` multiplica la suma por `orderSign`: los tres
    `get_foreign_total_*` de un reembolso llevan el signo del total local y las
    proporciones derivadas salen positivas.
  - Se quitan los `Math.abs` de `get_effective_foreign_multiplier` y
    `get_display_rate`: con los dos totales del mismo signo ya no hacen falta y
    solo escondían el error. Si un cambio de producto (reembolso a la tasa
    original más venta a la de hoy) deja los netos con signos opuestos, la
    proporción no es una tasa: `get_effective_foreign_multiplier` cae a la tasa
    viva, igual que ya hacía `get_display_rate`.
- **`static/src/overrides/models/payment_model.js`** (`set_foreign_amount`,
  rama sin tasa exacta): la proporción negativa era la que daba, por
  casualidad, el signo correcto al excedente de un reembolso. Ahora el pago de
  un reembolso toma el signo del reembolso aunque el cajero teclee el monto en
  positivo, y el excedente (una magnitud) se suma con el signo de la deuda,
  igual que la rama de tasa exacta. Las ventas no cambian.
- **`models/pos_order.py`**: `_process_saved_order` llama a
  `_align_foreign_signs` antes de marcar la orden pagada, crear los asientos de
  pago y facturar. Da a `foreign_amount_total` y a cada `foreign_amount` el
  signo de su monto local, conservando la magnitud. Cubre el PdV con el bundle
  viejo en caché, el wizard de devolución del backend (`pos.make.payment`, que
  copia el `foreign_amount_total` positivo de la original) y el Kiosko.
- **`migrations/19.0.1.20/post-align_refund_foreign_signs.py`**: aplica
  `_align_foreign_signs` a las órdenes de las sesiones que no estén cerradas,
  para que un reembolso guardado con el signo invertido antes de actualizar no
  rompa el cierre de su sesión. Las sesiones cerradas no se tocan.
- Manifiesto 1.19 → 1.20.

## Non-goals

- Corregir las órdenes ya guardadas con el signo invertido en sesiones cerradas
  (sus asientos ya están publicados).
- Límite conocido: en un cambio de producto con los netos de signos opuestos
  (local +15 Bs, foráneo −0,5 $), la guarda pone el foráneo en +0,5. Antes del
  fix se guardaba igual (+0,5), así que no es una regresión.
- Los extractos de efectivo del cierre descuadrados en alterno (H2) y el
  `foreign_rate` en 0 de los pagos (H7): changes propios.

## Impact

- Pantalla de pago y resúmenes: el total foráneo de un reembolso se muestra en
  negativo, igual que el local (antes "+11,60 $" con los Bs en negativo, parte
  de H9). El buffer del método foráneo propone "−11,60" en vez de "11,60".
  `l10n_ve_pos_igtf` suma total foráneo + IGTF foráneo, que ahora tienen el
  mismo signo.
- `l10n_ve_pos_mf` con la máquina fiscal en base foránea: la NC filtraba los
  pagos con `get_foreign_amount()` negativo y, como eran positivos, siempre
  repartía el total entre los métodos de la orden original. Ahora manda los
  pagos reales del reembolso. Hay que validarlo con la máquina fiscal.
- Tests: `tests/test_pos_refund_foreign_sign.py` (guarda del servidor),
  `static/tests/unit/pos_order_refund_sign.test.js` (signo en el origen) y la
  batería e2e de `binaural_pos_multicurrency` (integra-addons).
