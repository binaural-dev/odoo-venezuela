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

### Requirement: El parseo del monto no reinterpreta valores generados por el propio core

El parseo del precio recibido en `setUnitPrice` DEBE probar primero una
conversión nativa (`Number()`) antes de caer al parser sensible al locale.
Un valor de entrada con punto decimal puede venir de dos orígenes distintos:
lo que teclea el cajero (nunca lleva punto en `es_VE`, el numpad solo ofrece
la tecla de coma) o lo que arma el propio core al serializar un número
(`String(numero)`, que SIEMPRE usa punto, sin importar el locale activo). Si
se parseara ese segundo caso directo con el parser de locale, el punto se
leería como separador de miles.

#### Scenario: El core reasigna el monto como string con punto decimal

- GIVEN locale `es_VE` (coma decimal, punto de miles) y una línea de
  descuento con precio `-4842.69`
- WHEN `setUnitPrice` recibe el string `"-4842.69"` (con punto, no tecleado
  por el cajero)
- THEN el precio resultante es `-4842.69`
- AND NO es `-484269` (el error de multiplicar por 100)

### Requirement: "+/-" sobre la línea de descuento con el buffer vacío es un no-op

En modo precio, con el buffer del numpad recién limpio, pulsar "+/-" sobre la
línea de descuento NO DEBE alterar su monto. El core reconstruye ese caso
desde `selectedLine.prices.total_excluded_currency` (el monto sin impuesto)
en vez de `price_unit`; con un impuesto tax-included (como el de la línea de
descuento) eso no es el mismo número, así que el monto se encogería por el
factor del impuesto. Como el modelo ya garantiza que esta línea nunca queda
positiva, no hay signo que invertir.

#### Scenario: "+/-" con buffer vacío no cambia el monto del descuento

- GIVEN una línea de descuento seleccionada en modo precio, con el buffer del
  numpad vacío, y un impuesto tax-included asociado a la línea
- WHEN el cajero pulsa "+/-"
- THEN el precio de la línea de descuento no cambia

#### Scenario: "+/-" sigue funcionando normalmente en otras líneas y modos

- GIVEN una línea que no es la de descuento, o la línea de descuento en modo
  cantidad, o una línea de descuento en una orden de reembolso
- WHEN el cajero pulsa "+/-"
- THEN se aplica el comportamiento nativo del core (sin el no-op)
