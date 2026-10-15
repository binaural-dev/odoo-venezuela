# Spec delta: islr-retention-base-amount

## Nota de actualización (posterior a este change, no retocar el "Why" original)

Este spec describía el estado correcto al momento de #TI-15158. Dos de sus
afirmaciones ya no son ciertas tal cual están escritas, superadas por
trabajo posterior en la misma área (helpdesk #14548 y tarea #82491):

- **"usando `price_subtotal`"**: superado. El monto base (para el caso de
  2+ líneas con concepto ISLR) pasó de `price_subtotal` (moneda de la
  factura) a `abs(line.balance)` (monto ya resuelto en moneda de la
  compañía) - corrección de moneda para facturas en USD, donde
  `price_subtotal` no está en la misma moneda que el resto de los montos
  de la retención. Los valores numéricos de los escenarios de abajo siguen
  siendo correctos solo si la factura está en la moneda de la compañía
  (VEF); en USD, el campo fuente cambió aunque el resultado numérico pueda
  coincidir.
- **"Cuando hay una sola línea válida, la base sigue siendo el subtotal
  total de la factura... sin cambios"**: superado por la tarea #82491
  ("Crear un Check que haga configurable la base imponible de la retención
  de ISLR Proveedores"), que agregó el ajuste por compañía
  `islr_prioritize_product_subtotal_base` (default `False`, mantiene este
  comportamiento como default). Con el ajuste activo, la base para una
  sola línea pasa a ser el subtotal del producto/servicio en vez del total
  de la factura. El detalle completo de esa capability está en
  `openspec/changes/l10n-ve-payment-islr-retention-base-subtotal/`
  (histórico, sin actualizar) y en el commit `[IMP] ... hace configurable
  la base imponible de retención ISLR de Proveedores (82491)`.

Los requisitos de abajo quedan tal cual se escribieron originalmente, como
registro histórico de esa propuesta puntual - la nota de arriba es la
fuente de verdad sobre qué sigue vigente hoy.

## ADDED Requirements

### Requirement: El monto base de retención ISLR por línea usa el importe de la línea

El sistema SHALL calcular el monto base de retención ISLR de cada línea de
factura con concepto de pago asociado usando `price_subtotal` (precio
unitario × cantidad, con descuento aplicado), y SHALL NOT usar `price_unit`
sin multiplicar por cantidad ni aplicar descuento.

> Actualizado después de este change: la fuente pasó de `price_subtotal` a
> `abs(line.balance)` (ver nota de actualización arriba) - el requisito de
> fondo (no usar `price_unit` sin cantidad/descuento) sigue vigente.

Esto aplica quando la factura tiene más de una línea con concepto de pago
ISLR (`use_price_unit=True` en
`AccountMoveRetention._get_payment_concepts_from_invoice`). Cuando hay una
sola línea válida, la base sigue siendo el subtotal total de la factura
(`move_id.tax_totals["base_amount"]`) **por defecto** (ver nota de
actualización: desde #82491 es configurable por compañía).

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
- **AND** la factura está en la moneda de la compañía (VEF)
- **WHEN** se calculan los conceptos de pago de la factura
  (`_get_payment_concepts_from_invoice`)
- **THEN** el monto base de la primera línea es su `balance` (270.0),
  no su `price_unit` (100.0)
- **AND** el monto base de la segunda línea es su `balance` (200.0),
  no su `price_unit` (50.0)

#### Scenario: Factura con una sola línea ISLR, ajuste de base configurable desactivado (default)

- **GIVEN** una factura de proveedor con una única línea de servicio con
  concepto de pago ISLR asociado
- **AND** `company.islr_prioritize_product_subtotal_base` es `False`
  (default)
- **WHEN** se calculan los conceptos de pago de la factura
- **THEN** el monto base sigue siendo el subtotal total de la factura
  (comportamiento sin cambios respecto al momento de este change)

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
