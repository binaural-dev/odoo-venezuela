## Why

Al liquidar (o abonar) una orden de venta desde el PdV (`pos_sale`), las líneas de producto de la factura quedan
con el precio en moneda alterna en 0,00 (`foreign_price`, `foreign_subtotal`, `foreign_debit/credit/balance`).
La factura cuadra en alterno, pero su total alterno queda en el IVA solo: en `posconsultoria_ti16585`, la
INV/2026/0006 (pos.order 416, liquida S00006, tasa 600 Bs/USD) tiene la CxC en 0,30 USD cuando la orden cobró
2,30 USD (`pos.order.foreign_amount_total` y `pos.payment.foreign_amount`). Al conciliar con el pago quedan
2,00 USD de diferencia. Una venta normal del PdV no tiene el problema.

Causa: el commit del core `534aaac9114d` («[FIX] pos_sale: keep sale order unit prices when settling», en la
imagen 19.0-20261029) sobrescribe `PosOrderline.setUnitPrice` en `pos_sale`. Si la línea tiene
`sale_order_line_id`, asigna `price_unit` directo y no llama a `super`. El patch de `l10n_ve_pos` en
`setUnitPrice` es el único lugar del PdV que fija `foreign_price`, y queda debajo del de `pos_sale` porque
`l10n_ve_pos` no depende de `pos_sale`. La línea se sincroniza con `foreign_price = 0`, y
`pos.order._get_invoice_lines_values` copia ese 0 a la factura. La pantalla, el recibo y la máquina fiscal no
muestran el error, porque calculan el alterno al vuelo desde el precio en Bs.

Es el mismo tipo de defecto que el ticket #15106 (reembolsos creados sin `setUnitPrice`) y que el #16547 (líneas
de descuento global). Esta vez se corrige en el servidor para cualquier camino del PdV, no solo para uno.

## What Changes

- `l10n_ve_pos` (`pos.order.line`): al crear o actualizar una línea con precio unitario distinto de cero y sin
  precio alterno, el servidor lo completa con el cálculo del PdV: precio × tasa del PdV estampada en la orden (`pos.order.foreign_currency_rate`; en un
  reembolso, la de la venta original). No es la tasa de la orden de venta (`sale.order`) ni la del día, con su signo y la precisión "Foreign Product Price". Si la caja opera en la moneda
  alterna, el precio alterno es el precio unitario. Un precio alterno presente no se toca, y la regla de
  reembolso del #15106 (copiar el de la línea original) se aplica antes.
- `l10n_ve_pos` (`pos.order.line.write`): si una actualización cambia el precio unitario y no trae un precio
  alterno nuevo, se recalcula. Cubre el borrador que el PdV ya sincronizó (al abrir la pantalla de órdenes,
  por ejemplo) y cuyo precio se edita después en una línea de la orden de venta.
- `l10n_ve_pos` (`pos.order._get_invoice_lines_values`): red de seguridad. Una línea de orden sin precio alterno
  y con precio distinto de cero da en la factura el precio alterno calculado con la misma regla, no 0. Es una
  sola fórmula, compartida con el punto anterior y con el descuento global del PR odoo-venezuela#1649.
- Pruebas Python nuevas en `l10n_ve_pos`. Se ajustan dos pruebas del #15106 y una precondición del kiosko
  (`l10n_ve_pos_self_order`), que suponían que una línea de venta guardada con `foreign_price = 0` se quedaba
  en 0.
- Versión de `l10n_ve_pos`: el siguiente parche disponible en la rama destino.

## Capabilities

### New Capabilities

(ninguna)

### Modified Capabilities

- `l10n_ve_pos`: requirements nuevos para que el servidor complete el precio alterno de las líneas del PdV y lo
  recalcule cuando cambia el precio. Se modifica "La factura del PdV hereda la tasa de la orden" para agregar la
  red de seguridad.

## Non-goals y limitaciones

- **Frontend sin cambios.** Ningún consumidor del PdV depende del `foreign_price` guardado en el navegador
  (ver design.md, D6). Después de cada sincronización, el PdV recibe del servidor el valor ya completado.
- **Datos ya registrados.** Las facturas publicadas con alternos en 0 desde la actualización del core no se
  reprocesan. design.md trae la consulta para encontrarlas y las opciones de corrección, como decisión
  pendiente.
- **Precio alterno desfasado sin cambio de precio.** Si una línea trae un precio alterno distinto de cero pero
  calculado con otro precio, y en la misma actualización no cambia `price_unit`, no se detecta. Solo las líneas
  de descuento global se recalculan siempre (#1649).
- **Tasa cambiada entre sincronizaciones de un borrador.** El servidor escribe las líneas antes que la cabecera:
  una línea completada en la segunda sincronización usa la tasa de la primera. Pasa solo si la tasa de la caja
  cambió entre las dos.
- `pos.order.line.foreign_subtotal` y `foreign_total` siguen en 0, también en las ventas normales. Nadie los
  usa.

## Impact

- **Código:** `l10n_ve_pos/models/pos_order_line.py` (`create`, `write` y helpers nuevos),
  `l10n_ve_pos/models/pos_order.py` (`_get_invoice_lines_values`). No se cambian modelos, vistas, datos ni JS.
- **Pruebas:** archivo nuevo `l10n_ve_pos/tests/test_pos_line_foreign_price_backfill.py`. Se ajustan
  `l10n_ve_pos/tests/test_pos_refund_foreign_price.py` (2 pruebas) y
  `l10n_ve_pos_self_order/tests/test_kiosk_invoice_foreign_debit_credit.py` (una precondición).
- **Depende del PR #1662 (ticket 16547, descuento global, base `19.0`):** esta rama está apilada sobre la suya
  porque toca los mismos `create`/`write` y usa la misma fórmula. Este cambio extiende su código, y su
  `_sync_global_discount_foreign_price` pasa a usar el helper compartido. #1662 se mergea primero.
- **Change abierto `reembolso-precio-foraneo-linea`:** su requirement dice que el backfill de reembolso no toca
  las líneas de venta normales. Sigue siendo cierto para la copia desde la original, pero ahora la regla general
  sí completa una línea de venta guardada en 0. Este PR aclara ese texto en la spec de cambios de ese change (no
  lo archiva: le quedan pruebas de navegador abiertas), así que los dos se pueden archivar en cualquier orden.
- **Despliegue:** `-u l10n_ve_pos`, sin migración. Rige para las líneas que se sincronicen y las facturas que se
  generen después de actualizar.
