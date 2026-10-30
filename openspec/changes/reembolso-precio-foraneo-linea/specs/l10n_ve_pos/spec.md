## ADDED Requirements

### Requirement: Precio en moneda alterna de las líneas de reembolso

Cuando el PdV crea una línea de reembolso (una `pos.order.line` con `refunded_orderline_id`, creada por el core en `TicketScreen.onDoRefund`) y la línea llega sin precio en moneda alterna (`foreign_price` en 0), el sistema DEBE (MUST) reponer su `foreign_price` con el de la línea original que se reembolsa (`refunded_orderline_id.foreign_price`). El sistema NO DEBE (MUST NOT) sobrescribir un `foreign_price` que la línea ya traiga (p. ej. el que inyecta `_prepare_refund_data` en el reembolso de backend), ni tocar líneas de venta normales (sin `refunded_orderline_id`).

En consecuencia, el asiento de la Nota de Crédito —cuyas líneas de producto derivan su monto en moneda alterna del `foreign_price` de la línea de PdV vía `pos.order._get_invoice_lines_values`— DEBE (MUST) revertir EXACTAMENTE el monto en moneda alterna (USD) de la factura de origen, a la tasa del día de la venta y NO a la del día del reembolso, y NO DEBE (MUST NOT) dejar las líneas de producto en 0,00. Como red de seguridad, `_get_invoice_lines_values` DEBE (MUST) tomar el `foreign_price` de la línea original cuando la línea de reembolso llegue sin él.

La partida doble en la moneda base NO cambia, y el importe en Bs. de todas las líneas se mantiene igual. El IVA y la cuenta por cobrar de la NC quedan cuadrados en USD como consecuencia de que las líneas de producto traen el alterno correcto (el IVA deriva del subtotal foráneo y la cuenta por cobrar se computa como suma de las demás líneas).

#### Scenario: Reembolso con tasa distinta a la de la factura

- **WHEN** se factura una venta de PdV el día 1 (tasa R1) y se reembolsa la orden desde el PdV el día 2 (tasa R2 ≠ R1)
- **THEN** las líneas de producto del asiento de la NC registran el monto en moneda alterna (USD) calculado a la tasa R1 (el mismo que la factura de origen), no a R2 ni en 0,00, y el saldo en USD de la NC cuadra 1:1 contra la factura

#### Scenario: Reembolso de backend con precio foráneo ya presente

- **WHEN** se crea la línea de reembolso desde el backend (donde `_prepare_refund_data` ya rellena `foreign_price`)
- **THEN** el `foreign_price` de la línea se conserva sin cambios (el backfill no lo sobrescribe)

#### Scenario: Venta normal

- **WHEN** se crea una línea de venta normal (sin `refunded_orderline_id`)
- **THEN** su `foreign_price` no es alterado por el backfill de reembolso
