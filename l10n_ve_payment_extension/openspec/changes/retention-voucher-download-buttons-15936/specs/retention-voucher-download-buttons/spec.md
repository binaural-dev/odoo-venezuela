# Spec delta: retention-voucher-download-buttons

## ADDED Requirements

### Requirement: El documento debe ofrecer un botón de descarga por tipo de retención

El sistema SHALL mostrar en la cabecera de la vista del documento
(`account.move`) un botón de descarga del comprobante en PDF para cada tipo de
retención (IVA, ISLR y municipal). Cada botón SHALL mostrarse solo cuando el
documento tiene una retención emitida de ese tipo, y SHALL descargar el
comprobante con el formato propio de ese tipo.

#### Scenario: Documento con una retención de IVA emitida

- **GIVEN** un documento con una retención de IVA emitida
- **THEN** se muestra el botón "Download IVA voucher"
- **AND** no se muestran los botones de ISLR ni de municipal
- **WHEN** el usuario pulsa el botón
- **THEN** descarga el PDF con el formato del comprobante de IVA

#### Scenario: Documento con retenciones de varios tipos

- **GIVEN** un documento con retenciones emitidas de IVA, ISLR y municipal
- **THEN** se muestran los tres botones
- **AND** cada uno descarga el comprobante de su tipo

#### Scenario: Documento sin retenciones emitidas de un tipo

- **GIVEN** un documento sin retención emitida de un tipo, o solo con
  retenciones en borrador o anuladas de ese tipo
- **THEN** el botón de ese tipo no se muestra

### Requirement: Varias retenciones del mismo tipo se descargan juntas

Cuando el documento tiene varias retenciones emitidas del mismo tipo, el botón
SHALL descargar un único PDF con un comprobante por cada retención.

#### Scenario: Dos retenciones de ISLR emitidas sobre el mismo documento

- **GIVEN** un documento con dos retenciones de ISLR emitidas
- **WHEN** el usuario pulsa "Download ISLR voucher"
- **THEN** el PDF contiene el comprobante de cada una

### Requirement: La acción falla con un mensaje claro si no hay retención emitida

El sistema SHALL lanzar `UserError` si `action_download_retention_voucher` se
invoca sin retenciones emitidas del tipo pedido o con un tipo desconocido.

#### Scenario: Tipo sin retenciones emitidas

- **GIVEN** un documento sin retención municipal emitida
- **WHEN** se invoca la acción con el tipo `municipal`
- **THEN** se lanza `UserError` con el mensaje "There is no emitted retention
  voucher to download."

### Requirement: Las municipales fijan la fecha de entrega en la primera descarga

Para las retenciones municipales, el sistema SHALL escribir `date_emision` con la
fecha de hoy solo cuando está vacío, igual que el botón del Excel. Descargas
posteriores NO DEBEN modificarla.

#### Scenario: Primera descarga de un comprobante municipal

- **GIVEN** una retención municipal emitida sin `date_emision`
- **WHEN** se descarga su comprobante desde el documento
- **THEN** `date_emision` queda con la fecha de hoy

### Requirement: El formulario de cada retención debe ofrecer un botón de descarga cuando está emitida

El sistema SHALL mostrar en la cabecera del formulario de las retenciones de IVA,
ISLR y municipal un botón "Download voucher PDF", visible solo cuando la
retención está en estado `emitted`. Al pulsarlo, `action_print_retention_voucher_pdf`
SHALL devolver la acción de `retention_voucher_action` sobre esa retención y
lanzar `UserError` si la retención no está emitida.

#### Scenario: Retención emitida

- **GIVEN** una retención de cualquiera de los tres tipos en estado `emitted`
- **THEN** el formulario muestra el botón "Download voucher PDF"
- **WHEN** el usuario lo pulsa
- **THEN** descarga el PDF del comprobante con el formato de su tipo

#### Scenario: Retención en borrador o anulada

- **GIVEN** una retención en estado `draft` o `cancel`
- **THEN** el botón no se muestra

#### Scenario: Primera descarga de una retención municipal

- **GIVEN** una retención municipal emitida sin `date_emision`
- **WHEN** se pulsa el botón
- **THEN** `date_emision` queda con la fecha de hoy
- **AND** descargas posteriores no la modifican
