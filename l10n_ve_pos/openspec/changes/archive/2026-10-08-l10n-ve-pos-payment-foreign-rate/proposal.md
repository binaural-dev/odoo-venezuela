# Fix: los pagos del PdV llegaban con `foreign_rate` 0 (l10n_ve_pos)

## Why

Tarea 83148, hallazgo H7 de la prueba e2e del PdV multimoneda (01-oct-2026).
En una caja en Bs, los pagos que manda el PdV se guardaban con
`pos.payment.foreign_rate = 0`; solo los vueltos llevaban la tasa, porque los
crea el servidor y `_process_payment_lines` se la rellena (#15090).
`pos.payment._create_payment_moves` copia esa tasa al asiento de pago: quedaba
con `foreign_rate` y `foreign_inverse_rate` en 0 y `manually_set_rate`. El
alterno de sus líneas estaba bien (se fuerza desde `foreign_amount`), pero
cualquier recálculo (pasarlo a borrador y volver a publicar) lo dejaba en 0 $.
Reproducido en posv19 (06-oct, sesión 479): POSS/2026/0145 y 0147 con 0 / 0.

Causa: el core serializa los pagos anidados en la orden por recursión directa
(`deepSerialization` de `related_models/serialization.js`, valores crudos de los
campos), sin llamar a `PosPayment.serializeForORM`. El `foreign_rate` que ese
método añadía nunca salía del PdV, y el campo del registro se queda en el 0 con
que se crea. En Odoo 17 lo copiaba `_payment_fields`, que ya no existe.
`l10n_ve_pos_igtf` ya había resuelto lo mismo para sus campos inyectándolos en
los comandos de `payment_ids` desde `PosOrder.serializeForORM`.

## What Changes

- **`static/src/overrides/models/pos_order.js`**: `serializeForORM` llama a
  `_setPaymentForeignRates`, que pone `foreign_rate` en cada comando
  `[0, 0, vals]` / `[1, id, vals]` de `payment_ids`, emparejando por uuid, como
  `l10n_ve_pos_igtf` (`order_model.js`). La tasa es
  `get_effective_foreign_multiplier()`, la misma con la que el PdV calcula el
  `foreign_amount` de los pagos (en un reembolso, la de la venta original). No se
  escribe el campo reactivo en cada cambio de monto.
- **`static/src/overrides/models/payment_model.js`**: se quita el
  `foreign_rate` muerto de `serializeForORM`.
- **`models/pos_order.py`**: `_process_payment_lines` rellena los pagos que no
  son vuelto y llegan sin tasa (bundle anterior en caché, órdenes guardadas
  offline) con `_get_payment_foreign_rate`: la tasa de la orden original si es
  un reembolso, si no la de la orden. Un pago con tasa no se toca.
- **`views/pos_payment_views.xml`** y **`views/pos_order.xml`**: `foreign_rate`
  con 15 decimales; el multiplicador de una caja en Bs (0,001244…) se mostraba
  0,00. Solo en las vistas: `digits` en el campo cambiaría la columna de
  `double precision` a `numeric`.

## Non-goals

- Corregir la tasa de los pagos y asientos ya guardados (la cabecera es
  informativa; el alterno de las líneas es correcto).
- El vuelto conserva la tasa de la orden aunque sea de un reembolso: su
  `foreign_amount` también lo calcula el servidor con ella (`_amount_to_foreign`),
  y tasa y monto deben ir juntos.
- Los cruces del cierre: `l10n_ve_accountant` les pone la tasa de su fecha al
  crearlos (no llevan `manually_set_rate`), con o sin este cambio.
- La convención `foreign_rate` / `foreign_inverse_rate` de los asientos del PdV:
  change `l10n-ve-pos-move-rate-convention` (H18).
- En las cajas en otra moneda `binaural_pos_multicurrency` reescribe la tasa del
  pago (compañía → alterna) después de `super()`; no cambia.

## Impact

- Asientos de pago del PdV con tasa en vez de 0 / 0.
- Tests: `tests/test_pos_payment_foreign_rate.py` (relleno del servidor),
  `static/tests/unit/pos_order_payment_rate.test.js` (comandos de la orden) y
  la batería e2e de `binaural_pos_multicurrency` (`test_payment_foreign_rate`).
