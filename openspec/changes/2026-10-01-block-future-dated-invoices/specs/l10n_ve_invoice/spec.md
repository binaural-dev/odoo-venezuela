## ADDED Requirements

### Requirement: Ninguna fecha de factura, nota de crédito, nota de débito o recibo puede ser futura al confirmar

`action_post` DEBE (MUST) impedir confirmar cualquier documento que no sea un asiento contable puro (`move_type` distinto de `entry` -- en la práctica, `is_invoice(include_receipts=True)`: factura, nota de crédito, nota de débito o recibo, de venta o de compra) cuando `invoice_date`, `invoice_date_display` o `date` (fecha contable) sea posterior a la fecha del día (`fields.Date.context_today`), lanzando un error de validación que identifica el campo y la fecha en conflicto (constraint `_check_dates_not_in_future`). Ticket #15450.

La validación solo corre en `action_post`, no como `@api.constrains` de guardado: un documento en borrador con alguna de estas fechas en el futuro SÍ se puede crear y guardar -- queda bloqueado únicamente el intento de confirmarlo mientras la fecha siga siendo futura.

Un asiento contable (`move_type = 'entry'`) queda fuera del alcance: no tiene `invoice_date` ni `invoice_date_display` con sentido fiscal, y su `date` no se valida aquí.

Una nota de débito (`account.debit.note`) no es un modelo distinto: es un `account.move` con `debit_origin_id`, del mismo `move_type` que su documento origen, así que pasa por el mismo `action_post` y queda cubierta por este guard sin lógica adicional.

#### Scenario: Factura de venta con invoice_date futuro

- **WHEN** se confirma una factura de venta cuyo `invoice_date` es posterior a hoy
- **THEN** se lanza un error de validación indicando que esa fecha no puede ser posterior a hoy

#### Scenario: Nota de crédito con invoice_date_display futuro

- **WHEN** se confirma una nota de crédito de venta cuyo `invoice_date_display` es posterior a hoy
- **THEN** se lanza un error de validación

#### Scenario: Factura de compra con fecha contable futura

- **WHEN** se confirma una factura de proveedor cuyo `date` (fecha contable) es posterior a hoy
- **THEN** se lanza un error de validación

#### Scenario: Recibo de venta o de compra con fecha futura

- **WHEN** se confirma un recibo (`out_receipt`/`in_receipt`) cuyo `invoice_date` es posterior a hoy
- **THEN** se lanza el mismo error de validación que en una factura

#### Scenario: Nota de débito hereda el guard de su action_post

- **WHEN** se confirma una nota de débito (venta o compra) con alguna de sus tres fechas posterior a hoy
- **THEN** se lanza el mismo error de validación, sin código específico para notas de débito

#### Scenario: Un asiento contable puro no se valida

- **WHEN** se confirma un `account.move` con `move_type = 'entry'` y `date` posterior a hoy
- **THEN** la confirmación procede con normalidad; el guard no aplica a asientos

#### Scenario: Guardar un borrador con fecha futura no se bloquea

- **WHEN** se crea o guarda en borrador una factura, nota de crédito, nota de débito o recibo con alguna fecha futura, sin confirmarla
- **THEN** el guardado se permite; el bloqueo solo aplica al llamar `action_post`

#### Scenario: Fecha de hoy confirma sin error

- **WHEN** se confirma un documento cuyas tres fechas son hoy o anteriores
- **THEN** la confirmación procede con normalidad
