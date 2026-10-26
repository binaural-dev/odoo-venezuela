## ADDED Requirements

### Requirement: Precisión del precio unitario en moneda alterna

El precio unitario en moneda alterna de una línea del PdV (`pos.order.line.foreign_price`) DEBE (MUST) redondearse con la precisión decimal de catálogo **"Foreign Product Price"** (`decimal.precision`), NO con los decimales de la moneda (nivel monetario). En Odoo 19 esa precisión DEBE (MUST) leerse del recordset cargado en el cliente `this.models["decimal.precision"]` (buscando el registro por `name`), y NO del `this.pos.dp[...]` de Odoo 17 (que no existe en Odoo 19). Cuando la precisión de catálogo no esté disponible, el sistema PUEDE (MAY) usar como respaldo los decimales de la moneda alterna.

En consecuencia, el PdV persiste `foreign_price` a plena precisión de catálogo, y el asiento de la factura —que deriva el monto en moneda alterna de cada línea de ese `foreign_price` vía `pos.order._get_invoice_lines_values`— DEBE (MUST) sumar exactamente el total en moneda alterna que el PdV mostró y cobró, con cada línea consistente (`foreign_price × cantidad = subtotal foráneo`). El sistema NO DEBE (MUST NOT) redondear el precio unitario foráneo a los 2 decimales de la moneda antes de multiplicarlo por la cantidad, porque el error de redondeo se multiplica y descuadra la suma de las líneas contra el total cobrado.

Esto NO cambia los importes en la moneda base (Bs.), ni la partida doble base, ni los montos de IGTF (que viven en el asiento del pago). Aplica a las ventas nuevas del PdV; las órdenes ya sincronizadas con un `foreign_price` de menor precisión no se reprocesan.

#### Scenario: Venta con cantidad mayor que uno

- **WHEN** se vende un producto con cantidad > 1 cuyo precio unitario en moneda alterna no tiene un valor exacto a 2 decimales (p. ej. 11,2461) y se factura desde el PdV
- **THEN** la línea del asiento registra el subtotal en moneda alterna a partir del precio unitario a plena precisión (11,2461 × 4 = 44,98, no 11,25 × 4 = 45,00), y la suma de las líneas de la factura cuadra con el total en moneda alterna cobrado por el PdV

#### Scenario: Precisión de catálogo no disponible en el cliente

- **WHEN** el recordset `this.models["decimal.precision"]` no contiene el registro "Foreign Product Price"
- **THEN** el precio unitario foráneo se redondea con los decimales de la moneda alterna (respaldo), sin romper el flujo del PdV
