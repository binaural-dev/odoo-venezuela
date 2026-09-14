# Spec delta: islr-retention-base-amount

## ADDED Requirements

### Requirement: El monto base de retención ISLR por línea usa el importe de la línea

El sistema SHALL calcular el monto base de retención ISLR de cada línea de
factura con concepto de pago asociado usando `price_subtotal` (precio
unitario × cantidad, con descuento aplicado), y SHALL NOT usar `price_unit`
sin multiplicar por cantidad ni aplicar descuento.

Esto aplica quando la factura tiene más de una línea con concepto de pago
ISLR (`use_price_unit=True` en
`AccountMoveRetention._get_payment_concepts_from_invoice`). Cuando hay una
sola línea válida, la base sigue siendo el subtotal total de la factura
(`move_id.tax_totals["base_amount"]`), sin cambios.

Motivo: `price_unit` es el precio por unidad, ajeno a la cantidad y al
descuento de la línea. Usarlo como base imponible de una retención fiscal
produce un monto incorrecto en cualquier línea con cantidad ≠ 1 o descuento
≠ 0, con riesgo de incumplimiento fiscal para el cliente.

#### Scenario: Factura con dos líneas ISLR, cantidad y descuento distintos de 1/0

- **GIVEN** una factura de proveedor con dos líneas de servicio, cada una
  con un concepto de pago ISLR asociado
- **AND** la primera línea tiene cantidad 3, precio unitario 100 y
  descuento 10%
- **AND** la segunda línea tiene cantidad 5, precio unitario 50 y
  descuento 20%
- **WHEN** se calculan los conceptos de pago de la factura
  (`_get_payment_concepts_from_invoice`)
- **THEN** el monto base de la primera línea es su `price_subtotal` (270.0),
  no su `price_unit` (100.0)
- **AND** el monto base de la segunda línea es su `price_subtotal` (200.0),
  no su `price_unit` (50.0)

#### Scenario: Factura con una sola línea ISLR

- **GIVEN** una factura de proveedor con una única línea de servicio con
  concepto de pago ISLR asociado
- **WHEN** se calculan los conceptos de pago de la factura
- **THEN** el monto base sigue siendo el subtotal total de la factura
  (comportamiento sin cambios)

### Requirement: La corrección aplica por igual a la creación manual y automática de retención ISLR

El sistema SHALL usar el mismo cálculo de monto base
(`_get_payment_concepts_from_invoice`) tanto en el flujo manual
(`action_create_islr_from_invoice`) como en el automático
(`auto_create_islr_retention`), de modo que un fix en el cálculo de base
corrija ambos flujos sin duplicar lógica.

#### Scenario: Retención ISLR creada automáticamente desde una factura multi-línea

- **GIVEN** una factura de proveedor con más de una línea ISLR con
  cantidad y/o descuento distintos de 1/0
- **WHEN** se ejecuta `auto_create_islr_retention()`
- **THEN** cada línea de retención usa `price_subtotal` como base, igual
  que en el flujo manual
