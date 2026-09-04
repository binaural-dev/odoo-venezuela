# Proposal: Restringir descuentos positivos en el POS (Ticket 14352)

## Intent

En el POS V19, al seleccionar una **línea de descuento** (global o por línea) y
pulsar **"+/-"** en el numpad (modo precio), el precio negativo del descuento se
invierte a positivo, convirtiendo el descuento en un **recargo** sobre la orden y
la factura. El sistema debe **impedir** que una línea de descuento quede en
positivo.

## Scope

### In Scope
- Garantizar que la línea del producto de descuento (`pos.config.discount_product_id`)
  nunca quede con `price_unit > 0` en órdenes que no son de reembolso.
- Si el precio llega en positivo (por "+/-" o al teclear el monto en modo
  precio), se **fuerza a negativo** (`-|price|`) en `PosOrderline.setUnitPrice`,
  en vez de bloquear. Así el cajero puede cambiar el monto del descuento sin
  recibir una alerta en cada tecla, y nunca se convierte en recargo.

### Out of Scope
- El cambio de signo por **cantidad** ya está bloqueado por el guard existente
  `PosOrderline.setQuantity` (cantidades negativas fuera de reembolso).
- La visualización del descuento sobre base imponible (ticket/tarea aparte).
- El cálculo del descuento en sí.

## Approach

El "+/-" es `SWITCHSIGN` (`value: "-"`): en modo precio termina aplicando
`OrderSummary.setLinePrice(line, price)` → `PosOrderline.setUnitPrice(price)`. Se
intercepta en el modelo: si es la línea de descuento (no reembolso) y el precio
resultante sería positivo, se coacciona a `-|price|`. Coaccionar en lugar de
bloquear permite editar el monto del descuento con normalidad. La línea de
descuento se identifica por `pos.config.discount_product_id`; se respeta el flujo
de reembolsos vía el helper existente `_isRefundLine()`.

## Affected Areas

| Área | Impacto |
|------|---------|
| `l10n_ve_pos` modelo `pos.order.line` (JS) | `setUnitPrice` fuerza a negativo el precio de la línea de descuento (no reembolso); nuevo helper `_isDiscountProductLine` |

References: helpdesk.ticket 14352 — "Restringir descuentos positivos en POS V19"
