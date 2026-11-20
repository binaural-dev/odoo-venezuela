# debit-note-detection

## Purpose

Criterio único para decidir si un `account.move` es una nota de débito en los documentos fiscales de la
localización (comprobantes de retención, TXT de retenciones de IVA, libros de compras y ventas, PDF estándar y
formato libre). La ND nativa de Odoo (`account.debit.note`) nace en el mismo diario que su factura de origen,
que normalmente no tiene `is_debit`; por eso el diario solo no basta. Origen: ticket Helpdesk #16372.

## Requirements

### Requirement: La nota de débito se identifica por el documento

`account.move._is_debit_note()` DEBE (MUST) devolver verdadero cuando el documento tiene `debit_origin_id` o
su diario tiene `is_debit`, y DEBE devolver falso para cualquier nota de crédito (`out_refund`, `in_refund`).

#### Scenario: ND de proveedor nativa en el diario normal de compras

- **WHEN** se crea una ND con el asistente `account.debit.note` desde una factura de proveedor publicada
- **THEN** `_is_debit_note()` es verdadero aunque el diario no tenga `is_debit`

#### Scenario: Documento en un diario dedicado de ND

- **WHEN** un documento sin `debit_origin_id` se registra en un diario con `is_debit`
- **THEN** `_is_debit_note()` es verdadero

#### Scenario: Nota de crédito en un diario `is_debit`

- **WHEN** una nota de crédito se registra en un diario con `is_debit`
- **THEN** `_is_debit_note()` es falso y la nota sale como NC en comprobante, TXT y libros

### Requirement: Los documentos fiscales usan el criterio del documento

El comprobante de retención de IVA (número en la columna de ND, tipo `02-REG`, factura afectada = origen), la
columna TD del comprobante de ISLR, el TXT de retenciones de IVA (tipo `02`), los libros de compras y ventas
(tipo `ND`, `02-REG`, factura afectada) y los títulos del PDF estándar ("Nota de débito de proveedor") y del
formato libre ("NOTA DE DÉBITO") DEBEN (MUST) decidir "es ND" con `_is_debit_note()`.

#### Scenario: Comprobante de IVA de una ND de proveedor nativa

- **WHEN** se imprime el comprobante de retención de IVA de una ND de proveedor del diario normal
- **THEN** el número sale en la columna Nota de Débito, el tipo es `02-REG` y la factura afectada es su origen

#### Scenario: La ND imprime su propia fecha

- **WHEN** la ND se crea con una fecha posterior a la de su factura de origen
- **THEN** el comprobante y el TXT imprimen la fecha de la ND, y la tasa sigue siendo la de la fecha del origen

#### Scenario: Factura de proveedor normal

- **WHEN** se imprime el PDF estándar de una factura de proveedor sin `debit_origin_id` en un diario normal
- **THEN** el título sigue siendo el del núcleo ("Vendor Bill", con la traducción de `account`)

### Requirement: La ruta fiscal no cambia

La impresión fiscal y el Reporte Z (`l10n_ve_account_mf`, `l10n_ve_iot_mf`) DEBEN (MUST) seguir decidiendo por
`is_debit_journal`, porque el Reporte Z resume lo que la impresora fiscal imprimió.

#### Scenario: ND de cliente nativa con impresora fiscal

- **WHEN** una ND de cliente con `debit_origin_id` en un diario normal se imprime por la ruta fiscal
- **THEN** la impresora y el Reporte Z la tratan como antes (por el diario)
