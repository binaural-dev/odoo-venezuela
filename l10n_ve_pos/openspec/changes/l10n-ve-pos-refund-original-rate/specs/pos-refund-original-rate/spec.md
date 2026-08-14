# Spec delta: pos-refund-original-rate

## ADDED Requirements

### Requirement: Las líneas de reembolso convierten a divisa con la tasa de la orden original

El sistema SHALL usar el `foreign_currency_rate` congelado de la orden
ORIGINAL (`refunded_orderline_id.order_id.foreign_currency_rate`) al
calcular montos en moneda extranjera de una línea de `pos.order.line` cuyo
`refunded_orderline_id` apunta a una línea de otra orden ya sincronizada,
en lugar de la tasa viva de `pos.config`. Si la orden original no tiene un
`foreign_currency_rate` válido (`> 0`), el sistema SHALL usar la tasa viva
como respaldo (comportamiento sin cambios).

#### Scenario: Reembolso con la tasa BCV distinta a la de la venta original

- **GIVEN** una orden sincronizada vendida con `foreign_currency_rate = R1`
- **AND** hoy `pos.config.foreign_rate`/`foreign_inverse_rate` corresponde
  a una tasa distinta `R2`
- **WHEN** se crea una línea de reembolso de esa orden
  (`refunded_orderline_id` apunta a la línea original)
- **THEN** `get_foreign_price_with_tax()`, `get_foreign_price_without_tax()`,
  `get_foreign_unit_price()` y el resto de los `get_foreign_*` de la línea
  de reembolso se calculan usando `R1`, no `R2`

#### Scenario: Venta normal (no reembolso) no se ve afectada

- **GIVEN** una línea sin `refunded_orderline_id`
- **WHEN** se calculan sus montos en divisa
- **THEN** se sigue usando la tasa viva de `pos.config`
  (`order.localToForeign()`), sin cambios de comportamiento

#### Scenario: Orden original sin tasa congelada (dato legado)

- **GIVEN** una línea de reembolso cuya orden original tiene
  `foreign_currency_rate` en `0` o ausente
- **WHEN** se calculan sus montos en divisa
- **THEN** el sistema usa la tasa viva de `pos.config` como respaldo, sin
  lanzar error

### Requirement: El total en divisa de una orden de reembolso respeta la tasa original de cada línea

El sistema SHALL calcular `get_foreign_total_with_tax()`,
`get_foreign_total_without_tax()` y `get_foreign_total_tax()` de una orden
que contiene líneas de reembolso sumando el monto en divisa ya calculado
de cada línea (que respeta la tasa original por línea, ver requirement
anterior) en lugar de convertir el total local agregado con la tasa viva
de la orden. El sistema SHALL aplicar la misma tasa efectiva (proporción
entre el total en divisa y el total local) a `get_foreign_due()` y
`get_foreign_change()` de esa orden.

#### Scenario: Total de una orden de reembolso de una sola línea

- **GIVEN** una orden de reembolso con una única línea cuya orden original
  tiene `foreign_currency_rate = R1`, distinto de la tasa viva `R2`
- **WHEN** se muestra el total de la orden en la pantalla de pago
  (`foreignTotalDueText`)
- **THEN** el monto mostrado es `local_total * R1`, no `local_total * R2`

#### Scenario: Orden de reembolso con líneas de más de una orden original

- **GIVEN** una orden de reembolso que reutiliza un destino vacío y
  contiene líneas que refieren a dos órdenes originales distintas, con
  tasas congeladas `R1` y `R1'`
- **WHEN** se calcula el total en divisa de la orden
- **THEN** el resultado es la suma de cada línea convertida con su propia
  tasa (`R1` o `R1'`), no una única tasa aplicada a todo el total

#### Scenario: Orden sin líneas de reembolso no cambia de comportamiento

- **GIVEN** una orden de venta normal, sin ninguna línea con
  `refunded_orderline_id`
- **WHEN** se calculan sus totales en divisa
- **THEN** se sigue usando `order.localToForeign(local_total)` (tasa viva),
  sin cambios de comportamiento

### Requirement: El badge (G)/(E) se muestra junto al nombre del producto

El sistema SHALL mostrar "(G)" cuando el primer impuesto aplicable a la
línea (`tax_ids`, o si no hay, `product_id.taxes_id`) tiene `amount != 0`,
y "(E)" en caso contrario o si no hay impuestos aplicables. El cálculo
SHALL vivir en `pos.order.line` (`get_aliquot_type()`), consultado
directamente por el template de `Orderline` como `line.get_aliquot_type()`.

#### Scenario: Producto gravado

- **GIVEN** una línea cuyo primer impuesto aplicable tiene `amount != 0`
- **WHEN** se renderiza la línea en el PdV
- **THEN** se muestra "(G)" junto al nombre del producto

#### Scenario: Producto exento o sin impuestos

- **GIVEN** una línea sin impuestos aplicables, o cuyo primer impuesto
  tiene `amount == 0`
- **WHEN** se renderiza la línea en el PdV
- **THEN** se muestra "(E)" junto al nombre del producto

## REMOVED Requirements

### Requirement: Componente `Orderline` con lógica de tasa/reembolso propia

Se elimina `static/src/overrides/components/orderline/orderline.js`
(patch de `Orderline.prototype`, el componente OWL, no el modelo). Todo su
contenido (`get_rate`, `currency_rate_display`, `get_refund_orderline`,
`getDisplayData`, los wrappers `get_foreign_price_*`, `get_aliquot_type`)
dependía de `this.pos`/`this.order` — nunca definidos en el componente
`Orderline` de Odoo 19 — y no era invocado por ningún template ni otro
archivo JS del módulo. La funcionalidad real (montos en divisa, tasa
original en reembolsos, badge (G)/(E)) vive ahora exclusivamente en el
modelo `pos.order.line` (`pos_order_line.js`), consultado directamente por
`orderline.xml` como `line.<método>()`.
