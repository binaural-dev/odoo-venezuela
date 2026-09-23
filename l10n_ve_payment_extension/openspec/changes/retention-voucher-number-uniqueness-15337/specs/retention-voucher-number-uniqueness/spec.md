# Spec delta: retention-voucher-number-uniqueness

## ADDED Requirements

### Requirement: El número de comprobante de una retención debe ser único por compañía y tipo

El sistema SHALL impedir que dos registros `account.retention` de la misma
compañía y el mismo `type_retention` (`iva`, `islr`, `municipal`) tengan el
mismo `number`. `number` SHALL además excluirse de la duplicación
(`copy=False`), junto con `state`, `correlative`, `retention_line_ids` y
`payment_ids`, de modo que duplicar una retención produzca siempre un
registro en borrador, sin comprobante propio, sin líneas y sin pagos
asociados.

#### Scenario: Duplicar una retención emitida

- **GIVEN** una retención ISLR "Emitida", con `number` asignado, líneas y
  pagos
- **WHEN** se duplica desde la vista de lista
- **THEN** el duplicado queda en estado "Borrador"
- **AND** el duplicado recibe un `number` nuevo (no el mismo que el
  original)
- **AND** el duplicado no tiene `retention_line_ids` ni `payment_ids`

#### Scenario: Número repetido en el mismo tipo de retención

- **GIVEN** una retención ISLR con `number` = "X" en la compañía C
- **WHEN** se intenta crear o guardar otra retención ISLR con `number` =
  "X" en la misma compañía C
- **THEN** se lanza `ValidationError`, nombrando el comprobante y la
  retención en conflicto

#### Scenario: Mismo número en tipos de retención distintos (permitido)

- **GIVEN** una retención ISLR con `number` = "X" en la compañía C
- **WHEN** se crea una retención IVA con `number` = "X" en la misma
  compañía C
- **THEN** el sistema lo permite - IVA e ISLR usan secuencias de control
  independientes
