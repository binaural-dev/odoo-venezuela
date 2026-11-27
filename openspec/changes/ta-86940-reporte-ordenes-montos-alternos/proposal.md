## Why

Tarea https://www.binauraldev.com/odoo/project.task/86940. En el análisis de órdenes del
Punto de Venta (`report.pos.order`) solo se ven los montos en la moneda de la compañía (Bs). El
cliente necesita verlos también en $ para comparar ventas entre fechas, porque en Bs la
comparación se distorsiona con la tasa.

Los campos `foreign_subtotal` y `foreign_total` de `pos.order.line` no sirven de fuente: en 19.0
ni el PdV ni el servidor los escriben, y el reporte saldría en 0.

## What Changes

- `report.pos.order` agrega la moneda alterna de la compañía (`foreign_currency_id`) y dos
  medidas en esa moneda: `foreign_untaxed_total` (subtotal sin impuestos) y
  `foreign_total_billed` (total con impuestos).
- Las medidas se calculan en la vista SQL con los montos de la línea por la tasa congelada del
  pedido (`foreign_currency_rate`), igual que convierte el PdV. En un reembolso se usa la tasa
  de la venta original, que se alcanza por `refunded_orderline_id` (en 19.0
  `refunded_order_id` no se guarda en la base). Así la venta y su reembolso se anulan en $
  aunque se hagan en días con tasas distintas, igual que la factura y la nota de crédito.
- El signo sigue la regla de `price_total` del core: los reembolsos restan.
- Las vistas pivot y gráfico muestran las dos medidas, con la etiqueta
  «Subtotal <moneda>» y «Total <moneda>» según la moneda alterna de la compañía activa.

## Impact

- Módulo: `l10n_ve_pos` (modelo `report.pos.order`, vistas pivot y gráfico del análisis de
  órdenes, traducción `es_VE`).
- Datos: ninguno se migra; la vista SQL se recrea al actualizar el módulo y cubre las órdenes
  históricas que tengan `foreign_currency_rate`.
- Usuarios: quienes usan Punto de Venta > Informes > Órdenes.
- Limitaciones conocidas:
  - Un pedido sin `foreign_currency_rate` aparece con sus montos en Bs y 0 en la moneda alterna.
  - Si se filtran varias compañías con monedas alternas distintas, la medida suma montos de
    monedas distintas y la etiqueta muestra la moneda de la compañía activa.
