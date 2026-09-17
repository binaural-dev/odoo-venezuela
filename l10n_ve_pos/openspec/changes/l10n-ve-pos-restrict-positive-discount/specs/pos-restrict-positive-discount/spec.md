# Spec delta: pos-restrict-positive-discount

## ADDED Requirements

### Requirement: La línea de descuento nunca queda en positivo

El precio unitario de la línea cuyo producto es `pos.config.discount_product_id`
NO DEBE quedar en un valor positivo en una orden que no es de reembolso. Si se
intenta fijar un precio `> 0` (p. ej. vía "+/-" o al teclear el monto en modo
precio), se coacciona a `-|price|` (negativo), no se bloquea. El parseo del
precio recibido DEBE ser sensible al locale (separador decimal `,` en
`es_VE`), no solo `Number()`.

#### Scenario: "+/-" sobre una línea de descuento

- GIVEN una orden POS con una línea de descuento (precio negativo)
- WHEN el cajero selecciona esa línea y pulsa "+/-" en el numpad
- THEN el precio de la línea de descuento permanece negativo (no se convierte en recargo)
- AND no se muestra ninguna alerta

#### Scenario: Cambiar el monto del descuento con un entero

- GIVEN una línea de descuento seleccionada en modo precio
- WHEN el cajero teclea un nuevo monto (p. ej. `500`)
- THEN la línea de descuento queda con ese monto en negativo (`-500`), como descuento
- AND el cajero no recibe una alerta en cada tecla

#### Scenario: Cambiar el monto del descuento con decimales en locale es_VE

- GIVEN una línea de descuento seleccionada en modo precio, locale `es_VE`
- WHEN el cajero teclea `500,50` (coma como separador decimal)
- THEN la línea de descuento queda en `-500.5`, no en `500.5`

#### Scenario: Creación normal del descuento no se ve afectada

- GIVEN el botón de descuento (global o por línea) que crea la línea con precio negativo
- WHEN se agrega la línea de descuento
- THEN se crea normalmente con su precio negativo

### Requirement: Los reembolsos no se ven afectados

En líneas de reembolso real (`refunded_orderline_id`), en órdenes con preset
de devolución (`order_id.preset_id.is_return`) o en órdenes marcadas como
reembolso por el core (`order_id.isRefund` / `order_id.is_refund`), donde los
signos ya van invertidos por diseño, la coacción NO DEBE aplicarse.

#### Scenario: Línea en orden de reembolso con preset de devolución

- GIVEN una línea en una orden con `preset_id.is_return`
- WHEN se fija su precio
- THEN la coacción no la altera

#### Scenario: Descuento global en una orden reembolsada vía Órdenes → Reembolsar

- GIVEN una orden con `is_refund = true` (creada desde Órdenes → Reembolsar,
  sin preset de devolución) y un descuento global cuya línea sale
  legítimamente positiva
- WHEN se fija el precio de esa línea de descuento
- THEN la coacción no la altera (el precio positivo se respeta)

### Requirement: La garantía vive en el modelo, reforzada en el servidor

La coacción DEBE aplicarse en el modelo (`PosOrderline.setUnitPrice`), de modo
que el dato nunca quede positivo sin importar la vía por la que llegue el
precio. Como hay caminos del propio core que escriben `price_unit`
directamente sin pasar por `setUnitPrice`, el backend DEBE reforzar la misma
garantía con una validación de servidor sobre `pos.order.line`, con las
mismas exenciones que el guard de JS.

#### Scenario: El dato nunca queda positivo aunque el precio llegue por otra vía

- GIVEN cualquier ruta que intente fijar `price_unit > 0` en la línea de descuento (no reembolso)
- WHEN se ejecuta `setUnitPrice`
- THEN el precio resultante es negativo (`-|price|`)

#### Scenario: El servidor rechaza un precio positivo que se cuele sin pasar por el guard de JS

- GIVEN una línea del producto de descuento en una orden que no es de reembolso
- WHEN se escribe `price_unit` positivo directamente (RPC, sync del PdV, o edición manual)
- THEN `pos.order.line` lanza `ValidationError` y no permite guardar el registro
