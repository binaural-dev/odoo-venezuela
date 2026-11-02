# Spec delta: pos-refund-original-rate

## ADDED Requirements

### Requirement: Una orden de venta ya sincronizada se muestra con su tasa congelada

El sistema SHALL convertir a divisa los totales y el monto por línea de una
orden **finalizada** (`this.finalized`) que NO es de reembolso usando su
`foreign_currency_rate` congelado (la tasa a la que se vendió), en lugar de
la tasa viva de `pos.config`. Esto aplica a `get_foreign_total_with_tax()`,
`get_foreign_total_without_tax()`, `get_foreign_total_tax()` y al monto en
divisa de cada `pos.order.line` (`_localToForeignMoney`). Una orden viva en
construcción (no finalizada, o sin `foreign_currency_rate > 0`) SHALL seguir
usando la tasa viva sin cambios. Las órdenes de reembolso SHALL seguir
gobernadas por el requirement de líneas de reembolso (tasa del original por
línea), evaluado primero.

#### Scenario: Venta de otro día vista en el TicketScreen

- **GIVEN** una orden de venta finalizada con `foreign_currency_rate = R1`
- **AND** hoy `pos.config` corresponde a una tasa distinta `R2`
- **WHEN** se abre esa orden en el TicketScreen
- **THEN** `get_foreign_total_with_tax()`, `_without_tax()`, `_tax()` y el
  monto en divisa de cada línea se calculan con `R1`, no `R2`

#### Scenario: Orden viva en construcción no se ve afectada

- **GIVEN** la orden en curso en el ProductScreen/PaymentScreen
  (`finalized` falso)
- **WHEN** se calculan sus totales y montos en divisa
- **THEN** se sigue usando la tasa viva de `pos.config`
  (`order.localToForeign`), sin cambios de comportamiento

#### Scenario: Venta finalizada sin tasa congelada (dato legado)

- **GIVEN** una orden finalizada con `foreign_currency_rate` en `0` o ausente
- **WHEN** se calculan sus montos en divisa
- **THEN** el sistema usa la tasa viva como respaldo, sin lanzar error

### Requirement: La tasa mostrada de una orden finalizada concuerda con sus totales

El sistema SHALL calcular `get_display_rate()` de una orden **finalizada** a
partir de la tasa que sus propios montos en divisa usan: para una venta, su
`foreign_currency_rate` congelado; para un reembolso, la tasa efectiva
derivada de sus totales (`|total_divisa| / |total_local|`), que ya refleja
la tasa del original. Si no puede derivarla, o la orden no está finalizada,
el sistema SHALL usar el orden de candidatos previo (tasa viva de
`pos.config` primero, congelada como último respaldo).

#### Scenario: Tasa mostrada de una venta pasada

- **GIVEN** una venta finalizada con `foreign_currency_rate = R1` distinto
  de la tasa viva `R2`
- **WHEN** se muestra `get_display_rate_formatted()` en el TicketScreen
- **THEN** se muestra `R1` (normalizada a "1 divisa = X local"), no `R2`

#### Scenario: Tasa mostrada de una nota de crédito pasada

- **GIVEN** una orden de reembolso finalizada cuyos totales en divisa se
  calcularon con la tasa del original
- **WHEN** se muestra su tasa en el TicketScreen
- **THEN** la tasa mostrada coincide con esos totales (misma tasa efectiva),
  no con la tasa viva de hoy

#### Scenario: Orden en construcción conserva la tasa viva mostrada

- **GIVEN** la orden en curso (no finalizada)
- **WHEN** se muestra su tasa
- **THEN** se usa la tasa viva de `pos.config`, sin cambios de comportamiento
