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
de reembolsos vía el helper existente `_isRefundLine()` (que también exime
`order_id.isRefund`, no solo `refunded_orderline_id`/`preset_id.is_return`).

El precio que llega a `setUnitPrice` no siempre es un número: cuando el
cajero teclea el monto, es el buffer crudo del `number_buffer`, sensible al
locale (coma decimal en `es_VE`). El guard parsea con `_numberFromInput`
(generalización de `_quantityAsNumber`, que ya usa el `parseFloat` sensible
al locale de `@web/views/fields/parsers`) en vez de `Number()`.

Como refuerzo, hay caminos del core que escriben `price_unit` sin pasar por
`setUnitPrice` (`pos_discount` al aplicar el descuento, long-press de
`OrderSummary`), así que se añade una `@api.constrains` en `pos.order.line`
que replica la misma garantía en el servidor, con las mismas exenciones.

`_numberFromInput` prueba primero `Number()` nativo antes de caer al parser
de locale (mismo criterio que el propio `setUnitPrice` del core): un valor
con punto decimal puede venir de dos orígenes — lo que teclea el cajero
(nunca lleva punto en `es_VE`) o lo que arma el propio core al serializar un
número (`String(numero)`, siempre con punto). Parsear ese segundo caso
directo con el parser de locale multiplicaba el monto por 100 (el punto se
leía como separador de miles).

Por último, `OrderSummary.updateSelectedOrderline` se parchea para que "+/-"
con el buffer recién limpio, en modo precio, sobre la línea de descuento sea
un no-op: el core arma ese caso desde `selectedLine.prices.total_excluded_currency`
(monto sin impuesto) en vez de `price_unit`, y con un impuesto tax-included
(como el de la línea de descuento) eso encogía el monto del descuento por el
factor del impuesto. Como el modelo ya garantiza el signo, no hay nada que
invertir.

## Affected Areas

| Área | Impacto |
|------|---------|
| `l10n_ve_pos` modelo `pos.order.line` (JS) | `setUnitPrice` fuerza a negativo el precio de la línea de descuento (no reembolso), con parseo sensible al locale que prueba `Number()` nativo primero; nuevo helper `_isDiscountProductLine`; `_isRefundLine` exime también `order_id.isRefund` |
| `l10n_ve_pos` modelo `pos.order.line` (Python) | `@api.constrains` `_check_discount_price_not_positive` como refuerzo de servidor |
| `l10n_ve_pos` componente `OrderSummary` (JS) | `updateSelectedOrderline` hace no-op el "+/-" con buffer vacío sobre la línea de descuento |

References: helpdesk.ticket 14352 — "Restringir descuentos positivos en POS V19"
