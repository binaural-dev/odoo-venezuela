# Restricción de descuentos positivos en el POS

## Purpose

Impedir que una línea de descuento del POS se convierta en un recargo al
invertir su signo con el botón "+/-" del numpad, sin estorbar la edición normal
del monto del descuento.

## Requirements

### Requirement: La línea de descuento nunca queda en positivo

El precio unitario de la línea cuyo producto es `pos.config.discount_product_id`
NO DEBE quedar en un valor positivo en una orden que no es de reembolso. Si se
intenta fijar un precio `> 0` (p. ej. vía "+/-" o al teclear el monto en modo
precio), se coacciona a `-|price|` (negativo), no se bloquea.

#### Scenario: "+/-" sobre una línea de descuento

- GIVEN una orden POS con una línea de descuento (precio negativo)
- WHEN el cajero selecciona esa línea y pulsa "+/-" en el numpad
- THEN el precio de la línea de descuento permanece negativo (no se convierte en recargo)
- AND no se muestra ninguna alerta

#### Scenario: Cambiar el monto del descuento

- GIVEN una línea de descuento seleccionada en modo precio
- WHEN el cajero teclea un nuevo monto (p. ej. `500`)
- THEN la línea de descuento queda con ese monto en negativo (`-500`), como descuento
- AND el cajero no recibe una alerta en cada tecla

#### Scenario: Creación normal del descuento no se ve afectada

- GIVEN el botón de descuento (global o por línea) que crea la línea con precio negativo
- WHEN se agrega la línea de descuento
- THEN se crea normalmente con su precio negativo

### Requirement: Los reembolsos no se ven afectados

En órdenes de reembolso (`_isRefundLine()`), donde los signos ya van invertidos
por diseño, la coacción NO DEBE aplicarse.

#### Scenario: Línea en orden de reembolso

- GIVEN una línea en una orden de reembolso
- WHEN se fija su precio
- THEN la coacción no la altera

### Requirement: La garantía vive en el modelo

La coacción DEBE aplicarse en el modelo (`PosOrderline.setUnitPrice`), de modo
que el dato nunca quede positivo sin importar la vía por la que llegue el precio.

#### Scenario: El dato nunca queda positivo aunque el precio llegue por otra vía

- GIVEN cualquier ruta que intente fijar `price_unit > 0` en la línea de descuento (no reembolso)
- WHEN se ejecuta `setUnitPrice`
- THEN el precio resultante es negativo (`-|price|`)
