# Spec delta: retention-voucher-number-uniqueness

## ADDED Requirements

### Requirement: El número de comprobante de una retención debe ser único por partner, dirección y tipo

El sistema SHALL impedir que dos registros `account.retention` activos
(`state != 'cancel'`) del mismo `partner_id`, la misma dirección del
comprobante (`in_*` agrupado vs. `out_*` agrupado) y el mismo
`type_retention` (`iva`, `islr`, `municipal`) tengan el mismo `number`,
dentro de la misma compañía. `number` SHALL además excluirse de la
duplicación (`copy=False`), junto con `state`, `correlative`,
`retention_line_ids` y `payment_ids`, de modo que duplicar una retención
produzca siempre un registro en borrador, sin comprobante propio, sin
líneas y sin pagos asociados.

El alcance es por partner y dirección - no global a la compañía - porque
proveedor y cliente (y cada partner entre sí) numeran sus comprobantes en
series independientes: la de proveedor sale de nuestra secuencia interna
`no_gap`, la de cliente la entrega el cliente con su propio correlativo.

#### Scenario: Duplicar una retención emitida

- **GIVEN** una retención ISLR "Emitida", con `number` asignado, líneas y
  pagos
- **WHEN** se duplica desde la vista de lista
- **THEN** el duplicado queda en estado "Borrador"
- **AND** el duplicado recibe un `number` nuevo (no el mismo que el
  original)
- **AND** el duplicado no tiene `retention_line_ids` ni `payment_ids`

#### Scenario: Número repetido para el mismo partner, dirección y tipo de retención

- **GIVEN** una retención ISLR de proveedor (`in_invoice`) con `number` =
  "X" para el partner P en la compañía C
- **WHEN** se intenta crear o guardar otra retención ISLR de proveedor
  con `number` = "X" para el mismo partner P en la misma compañía C
- **THEN** se lanza `ValidationError`, nombrando el comprobante y la
  retención en conflicto

#### Scenario: Mismo número en tipos de retención distintos (permitido)

- **GIVEN** una retención ISLR con `number` = "X" en la compañía C
- **WHEN** se crea una retención IVA con `number` = "X" en la misma
  compañía C
- **THEN** el sistema lo permite - IVA e ISLR usan secuencias de control
  independientes

#### Scenario: Mismo número entre partners distintos (permitido)

- **GIVEN** una retención ISLR de proveedor con `number` = "X" para el
  partner P1 en la compañía C
- **WHEN** se crea otra retención ISLR de proveedor con `number` = "X"
  para el partner P2 en la misma compañía C
- **THEN** el sistema lo permite - cada partner numera sus propios
  comprobantes

#### Scenario: Mismo número entre retención de proveedor y de cliente (permitido)

- **GIVEN** una retención ISLR de proveedor (`in_invoice`) con `number` =
  "X" para el partner P en la compañía C
- **WHEN** se crea una retención ISLR de cliente (`out_invoice`) con
  `number` = "X" para el mismo partner P en la misma compañía C
- **THEN** el sistema lo permite - proveedor y cliente numeran en series
  independientes

#### Scenario: Retención anulada no cuenta como duplicado

- **GIVEN** una retención ISLR de proveedor anulada (`state = 'cancel'`)
  con `number` = "X" para el partner P en la compañía C
- **WHEN** se crea otra retención ISLR de proveedor con `number` = "X"
  para el mismo partner P en la misma compañía C
- **THEN** el sistema lo permite - una retención anulada no reserva su
  número
