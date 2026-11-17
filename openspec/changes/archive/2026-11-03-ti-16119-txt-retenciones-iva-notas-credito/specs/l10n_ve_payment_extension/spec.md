## MODIFIED Requirements

### Requirement: Exportación TXT de retenciones IVA para el SENIAT

El wizard `wizard.retention.iva` DEBE (MUST) validar antes de generar el TXT que exista rango de fechas, que la compañía tenga RIF (`vat`) y que existan comprobantes emitidos en el período con `type_retention = iva` y `type` `in_invoice` o `in_refund` de la compañía activa, filtrando por el campo `date` (fecha del comprobante) y no por la fecha contable; los comprobantes de proveedor de tipo `in_debit` quedan fuera tanto del conteo como del archivo. El conteo del wizard y la búsqueda del controlador comparten un único dominio (`_get_retention_iva_domain`). El tipo de documento es `01` para facturas, `03` para notas de crédito (`in_refund`, con el documento afectado tomado de `reversed_entry_id`) y `02` para notas de débito, que se reconocen por el diario `is_debit` y cuyo comprobante es `in_invoice`; el documento afectado es `0` cuando no hay documento origen y el número de control sale vacío si el documento no lo tiene. El archivo se entrega por el controlador `/web/binary/download_retention_iva_txt` con una fila por línea de retención, separada por tabuladores en orden fijo (RIF del agente tomado del partner de la compañía, período `AAAAMM`, fecha de factura, tipo de operación "C", tipo de documento, RIF del proveedor con `prefix_vat`, número de documento, número de control, monto total, base imponible, IVA retenido, documento afectado, número de comprobante, monto exento, alícuota y número de expediente "0"), usando los montos en moneda alterna cuando la moneda base de la compañía no es VEF.

#### Scenario: Período sin retenciones

- **WHEN** se genera el TXT de un período sin comprobantes IVA de proveedor emitidos
- **THEN** se lanza un `UserError` indicando que no se encontraron retenciones en el período

#### Scenario: Período con solo retenciones sobre notas de crédito

- **WHEN** en el período únicamente existen comprobantes IVA emitidos con `type = in_refund`
- **THEN** el wizard no lanza el error de período sin retenciones y el archivo trae una fila por cada línea de esos comprobantes

#### Scenario: Facturas y notas de crédito en el mismo período

- **WHEN** en el período existen comprobantes IVA emitidos de una factura y de una nota de crédito de proveedor
- **THEN** el TXT incluye ambos; la fila de la nota de crédito lleva tipo de documento `03`, el número de la factura revertida como documento afectado y base e IVA retenido en positivo

#### Scenario: Nota de débito sin documento origen

- **WHEN** el comprobante corresponde a una nota de débito (diario `is_debit`) sin `debit_origin_id`
- **THEN** la fila lleva tipo de documento `02` y `0` como documento afectado

#### Scenario: Compañía sin RIF

- **WHEN** se genera el TXT y la compañía no tiene `vat`
- **THEN** se lanza un `UserError` indicando la falta del RIF
