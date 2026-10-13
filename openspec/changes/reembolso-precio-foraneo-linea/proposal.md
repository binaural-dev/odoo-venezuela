## Why

En el PdV con doble moneda (Bs. base + USD alterna), el reembolso (Nota de Crédito) de una factura de PdV genera un asiento con las **líneas de producto en 0,00** en la moneda alterna (USD), dejando toda la NC descuadrada en USD (los productos aportan 0, mientras IVA y cuenta por cobrar sí traen alterno). La causa: en Odoo 19 el core crea la línea de reembolso en el frontend (`TicketScreen.onDoRefund`) con un `create` directo que NO pasa por el override JS `setUnitPrice` —única vía que fija `foreign_price` en el cliente—, así que la línea se sincroniza con `foreign_price = 0`. Ese 0 se propaga al asiento: `pos.order._get_invoice_lines_values` copia `pos.order.line.foreign_price` a la línea contable, y con `foreign_price = 0` el `foreign_subtotal`/`foreign_debit` de los productos queda en 0. El hook `pos.order.line._prepare_refund_data` sí repone `foreign_price`, pero solo interviene en el reembolso de backend, no en el flujo de caja. (Ticket #15106; síntoma emparentado con #15123.)

## What Changes

- `l10n_ve_pos`: sobrescribir `pos.order.line.create` para reponer `foreign_price` en las líneas de reembolso a partir de la línea original que se reembolsa (`refunded_orderline_id`) cuando la línea llega sin precio foráneo. Así la NC revierte EXACTAMENTE el precio unitario en USD congelado de la factura de origen (tasa del día de la venta), no 0 ni la tasa del día del reembolso. No sobrescribe un `foreign_price` ya presente (respeta el que inyecta `_prepare_refund_data` en el backend).
- `l10n_ve_pos`: red de seguridad en `pos.order._get_invoice_lines_values`: al construir la línea contable de una NC, si la línea de PdV es de reembolso y llega con `foreign_price` ausente, tomar el de la línea original, para no volver a poner el alterno en cero por ninguna vía (incluidas líneas ya sincronizadas antes del backfill).

## Impact

- Specs afectadas: `l10n_ve_pos` (nueva requirement "Precio en moneda alterna de las líneas de reembolso").
- Código: `l10n_ve_pos/models/pos_order_line.py` (override de `create`), `l10n_ve_pos/models/pos_order.py` (fallback en `_get_invoice_lines_values`). Bump de manifest 1.12 → 1.13.
- Es un precio **unitario** (independiente de la cantidad): cubre reembolsos parciales, combos y descuentos (el descuento se aplica en el cómputo del subtotal de la línea contable). No cambia importes en Bs., ni la partida doble base, ni la lógica de sincronización/facturación de ventas normales (sin `refunded_orderline_id` no se toca nada). El IVA y la cuenta por cobrar de la NC cuadran solos una vez los productos traen el alterno correcto (el IVA deriva del `foreign_subtotal` y la CxC se computa como suma de las demás líneas).
- Datos existentes: los reembolsos ya sincronizados con `foreign_price = 0` no se reprocesan por el override de `create`; la red de seguridad en `_get_invoice_lines_values` los corrige si se facturan después de este cambio.
