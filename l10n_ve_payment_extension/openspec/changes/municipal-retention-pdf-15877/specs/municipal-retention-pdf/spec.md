# Spec delta: municipal-retention-pdf

## ADDED Requirements

### Requirement: El comprobante de retención municipal debe poder imprimirse en PDF

El sistema SHALL generar el PDF del comprobante de una retención municipal
emitida (`retention_voucher_action`) con un formato propio de comprobante de
impuesto a las actividades económicas, sin lanzar el error "las retenciones
municipales no tienen recibo PDF". El despachador
`retention_voucher_template` SHALL usar `report_municipal_customer` para las
retenciones con `type_retention = 'municipal'` y conservar los formatos de IVA
e ISLR para el resto.

#### Scenario: Imprimir una retención municipal emitida

- **GIVEN** una retención municipal en estado `emitted`
- **WHEN** se imprime el comprobante de retención en PDF
- **THEN** el PDF muestra el título de actividades económicas
- **AND** no usa el formato de ISLR ni lanza un error

#### Scenario: Lote con retenciones de IVA y municipales

- **GIVEN** una retención de IVA y una municipal, ambas emitidas
- **WHEN** se imprimen juntas en un solo PDF
- **THEN** cada una sale con su propio formato

### Requirement: El PDF municipal debe mostrar los mismos datos que el Excel

El sistema SHALL obtener la cabecera del PDF de
`municipal.retention.xlsx._get_tax_authorities_record` y las filas de
`get_xlsx_municipal_retention`, con las mismas columnas, el mismo orden, la
misma selección de moneda y el mismo total retenido, de modo que cualquier
cambio u override de esos métodos se refleje en ambos comprobantes. El formato
de montos y alícuota SHALL decidirse por el nombre de la columna.

#### Scenario: Filas y total iguales al Excel

- **GIVEN** una retención municipal emitida con una línea
- **WHEN** se prepara el comprobante en PDF
- **THEN** las nueve columnas, las filas y el total coinciden con los del Excel
- **AND** la alícuota se muestra como porcentaje con dos decimales

#### Scenario: Cabecera de la autoridad tributaria

- **GIVEN** una compañía con nombre de autoridad tributaria y número de
  licencia de actividades económicas configurados
- **WHEN** se imprime el comprobante municipal
- **THEN** el nombre de la autoridad aparece en mayúsculas en el título
- **AND** el número de licencia aparece en el bloque del agente de retención

### Requirement: La fecha de entrega depende del ajuste de la compañía

El sistema SHALL mostrar "FECHA DE EMISIÓN O TRANSACCIÓN" siempre y "FECHA DE
ENTREGA" solo cuando `hide_issue_date_of_municipal_withholding_receipt` está
desactivado. Si `date_emision` está vacío, SHALL mostrarse `--` y el sistema
NO DEBE escribir ningún dato en la retención al renderizar.

#### Scenario: Fecha de entrega oculta

- **GIVEN** una compañía con la fecha de entrega oculta
- **WHEN** se imprime el comprobante municipal
- **THEN** solo aparece la fecha de emisión o transacción

#### Scenario: Fecha de entrega vacía

- **GIVEN** una retención emitida sin `date_emision` y la fecha de entrega visible
- **WHEN** se imprime el comprobante municipal
- **THEN** la fecha de entrega se muestra como `--`
- **AND** `date_emision` sigue vacío

### Requirement: El comprobante municipal se imprime en papel vertical

El sistema SHALL usar el paperformat A4 vertical
`paper_format_retention_municipal_voucher` cuando todas las retenciones
seleccionadas son municipales, y conservar el paperformat horizontal original
en cualquier otro caso.

#### Scenario: Lote solo con retenciones municipales

- **GIVEN** una o varias retenciones municipales emitidas
- **WHEN** se imprime el comprobante
- **THEN** el PDF sale en formato A4 vertical

#### Scenario: Lote con otros tipos de retención

- **GIVEN** un lote que incluye una retención de IVA o de ISLR
- **WHEN** se imprime el comprobante
- **THEN** el PDF conserva el formato A4 horizontal

### Requirement: Los comprobantes en borrador siguen bloqueados

El sistema SHALL seguir impidiendo la descarga del PDF de una retención
municipal en estado `draft`, igual que para IVA e ISLR.

#### Scenario: Imprimir una retención municipal en borrador

- **GIVEN** una retención municipal en estado `draft`
- **WHEN** se intenta imprimir el comprobante en PDF
- **THEN** el sistema lanza `ValidationError`
