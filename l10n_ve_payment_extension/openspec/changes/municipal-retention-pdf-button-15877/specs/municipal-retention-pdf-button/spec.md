# Spec delta: municipal-retention-pdf-button

## ADDED Requirements

### Requirement: El formulario de la retención municipal debe ofrecer un botón para descargar el PDF

El sistema SHALL mostrar en la cabecera del formulario de la retención
municipal un botón "Print municipal retention PDF" en cualquier estado
(`draft`, `emitted` y `cancel`), igual que el botón del Excel. Al pulsarlo,
`action_print_municipal_retention_pdf` SHALL devolver la acción de
`retention_voucher_action` sobre esa retención.

#### Scenario: Descargar el PDF desde el formulario

- **GIVEN** una retención municipal en estado `emitted`
- **WHEN** el usuario pulsa "Print municipal retention PDF"
- **THEN** el sistema devuelve la acción del reporte
  `l10n_ve_payment_extension.retention_voucher_template` sobre esa retención

#### Scenario: Retención en borrador o anulada

- **GIVEN** una retención municipal en estado `draft` o `cancel`
- **THEN** el botón se muestra
- **AND** el PDF se genera sin restricción

### Requirement: El PDF de una retención municipal en borrador no está bloqueado

El sistema SHALL permitir descargar el PDF de una retención municipal en
estado `draft`. Esto modifica el requisito de `municipal-retention-pdf-15877`
(bloqueo de borradores) solo para el tipo `municipal`: las retenciones de IVA e
ISLR en borrador siguen bloqueadas por `ir.actions.report._render_qweb_pdf`.

#### Scenario: PDF de una retención municipal en borrador

- **GIVEN** una retención municipal en estado `draft`
- **WHEN** se imprime el comprobante en PDF
- **THEN** el PDF se genera sin error

#### Scenario: PDF de una retención de IVA en borrador

- **GIVEN** una retención de IVA en estado `draft`
- **WHEN** se imprime el comprobante en PDF
- **THEN** el sistema lanza `ValidationError`

### Requirement: La primera impresión fija la fecha de entrega

El sistema SHALL escribir `date_emision` con la fecha de hoy solo cuando está
vacío, igual que el botón del Excel, de modo que ambos comprobantes muestren la
misma fecha de entrega. Impresiones posteriores NO DEBEN modificarla.

#### Scenario: Primera impresión

- **GIVEN** una retención municipal emitida sin `date_emision`
- **WHEN** se pulsa el botón del PDF
- **THEN** `date_emision` queda con la fecha de hoy

#### Scenario: Impresión repetida

- **GIVEN** una retención municipal con `date_emision` ya fijada
- **WHEN** se pulsa el botón del PDF
- **THEN** `date_emision` conserva su valor
