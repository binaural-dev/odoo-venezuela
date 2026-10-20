# Spec delta: municipal-retention-pdf-button

## ADDED Requirements

### Requirement: El formulario de la retención municipal debe ofrecer un botón para descargar el PDF

El sistema SHALL mostrar en la cabecera del formulario de la retención
municipal un botón "Print municipal retention PDF", oculto cuando la retención
está en `draft`. Al pulsarlo, `action_print_municipal_retention_pdf` SHALL
devolver la acción de `retention_voucher_action` sobre esa retención.

#### Scenario: Descargar el PDF desde el formulario

- **GIVEN** una retención municipal en estado `emitted`
- **WHEN** el usuario pulsa "Print municipal retention PDF"
- **THEN** el sistema devuelve la acción del reporte
  `l10n_ve_payment_extension.retention_voucher_template` sobre esa retención

#### Scenario: Retención en borrador

- **GIVEN** una retención municipal en estado `draft`
- **THEN** el botón no se muestra
- **AND** imprimir el PDF por otra vía sigue lanzando `ValidationError`

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
