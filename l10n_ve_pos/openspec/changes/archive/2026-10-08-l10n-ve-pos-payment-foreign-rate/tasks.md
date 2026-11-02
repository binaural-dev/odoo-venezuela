# Tasks

## 1. Tests

- [x] 1.1 `tests/test_pos_payment_foreign_rate.py`: relleno de venta y de
      reembolso (tasa de la original), pago con tasa intacto
- [x] 1.2 `static/tests/unit/pos_order_payment_rate.test.js`: comandos de
      `payment_ids` con la tasa efectiva, comandos ajenos, reembolso, sin pagos
      y el `serializeForORM` real de la orden (cae si se quita la llamada)
- [x] 1.3 Batería e2e de `binaural_pos_multicurrency`: el `assertKnownBug` de H7
      pasa a aserción

## 2. Corrección

- [x] 2.1 `pos_order.js`: `_setPaymentForeignRates` desde `serializeForORM`
- [x] 2.2 `payment_model.js`: quitar el `foreign_rate` muerto de
      `serializeForORM`
- [x] 2.3 `pos_order.py`: relleno en `_process_payment_lines` con
      `_get_payment_foreign_rate`
- [x] 2.4 Vistas de pagos y de la orden: `foreign_rate` con 15 decimales
      (en una caja en Bs se veía 0,00); en la vista y no en el campo, que con
      `digits` pasaría la columna a `numeric` y reescribiría la tabla en el `-u`

## 3. Verificación

- [x] 3.1 Rojo antes del fix (relleno: 0 en vez de 36,5 y 30; hoot: `_setPaymentForeignRates` no existe; capa A: pagos con 0) y verde después. Suites completas (06-oct, BD nuevas): `l10n_ve_pos` 100/100, `l10n_ve_pos_igtf` 6/6, capa A de `binaural_pos_multicurrency` 65/69 (los 3 tours por el dbfilter de `./odoo test` y `test_refund_keeps_original_rate` por `l10n_ve_stock`, previos), tours con `--db-filter` 3/3, hoot 5/5 (el test del `serializeForORM` real cae si se quita la llamada). Fallo hoot previo ajeno: `payment_model › snap solo dentro de un paso foráneo` (origin/19.0, #15114; 0,40000000000009 > 0,4)
- [x] 3.2 Navegador (posv19, Caja VES Prueba/00225, sesión 479): el comando anidado del pago lleva `foreign_rate` 0,001244802947693; venta 000004 (Producto IVA16 10 USD, efectivo Bs 9.318,74) → pago con esa tasa (antes 0, órdenes 000001–000003) y la vista del pago la muestra completa
