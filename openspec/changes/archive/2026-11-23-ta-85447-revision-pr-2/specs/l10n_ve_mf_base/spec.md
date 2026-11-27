## MODIFIED Requirements

### Requirement: Motivo de un resultado desconocido

Un `printed: null` DEBE (MUST) traer `reason`: `no_response` si la máquina no respondió el estado o S1 (en `verifyDocument`, tras 3 consultas de estado); `document_open` si una nota de crédito o de débito no quedó en reposo después del `7`; `other_printer` si el serial de S1 no es el de la foto (se mira antes que el número); y `unattributable` si el número avanzó más de uno, los contadores no cuadran o S1 respondió sin el contador del documento.

#### Scenario: Se emitió otro documento en el medio

- **WHEN** al verificar el número avanzó dos o más
- **THEN** el resultado es `printed: null` con `reason: "unattributable"`

#### Scenario: Otra máquina

- **WHEN** el serial de S1 no coincide con el de la foto
- **THEN** el resultado es `printed: null` con `reason: "other_printer"`

#### Scenario: S1 sin el contador del documento

- **WHEN** al verificar S1 responde, pero sin el número del tipo de documento
- **THEN** el resultado es `printed: null` con `reason: "unattributable"`, y no `no_response`: esperar a la máquina no lo resuelve

#### Scenario: Máquina muda tras el cierre

- **WHEN** un pago se envió y S1 no responde al terminar
- **THEN** el resultado es `printed: null` con `reason: "no_response"` y el error original en `original_error`

#### Scenario: Nota de crédito abierta después del 7

- **GIVEN** una nota de crédito con un pago enviado que falla, y la máquina sigue con el documento abierto después del `7`, el `9` y el `199`
- **WHEN** se averigua el resultado
- **THEN** es `printed: null` con `reason: "document_open"` sin comparar S1 (no está medido que S1 cuente una NC o ND abierta), y se vuelve a verificar antes de la siguiente impresión

#### Scenario: NC o ND que acepta el 7 y sigue abierta

- **GIVEN** una nota de crédito o de débito con un pago enviado, y la máquina en transacción
- **WHEN** la máquina responde ACK al `7` pero sigue en transacción (con pagos, el `7` no anula el documento: sigue en la totalización, según el manual de la TFHKA)
- **THEN** el resultado es `printed: null` con `reason: "document_open"` sin leer S1

#### Scenario: NC que el 7 deja en reposo

- **WHEN** después del `7` la máquina queda en reposo
- **THEN** se compara S1 como antes: mismo número sin cierre aceptado es `printed: false`, y el número siguiente sin cierre aceptado es `unattributable`

#### Scenario: NC muda después del 7

- **WHEN** la máquina no responde el estado después del `7`
- **THEN** el resultado es `printed: null` con `reason: "no_response"` sin leer S1

#### Scenario: Factura abierta después del 7

- **WHEN** lo mismo pasa con una factura, haya o no aceptado el `7`
- **THEN** se compara S1 como siempre: está medido que S1 ya cuenta la factura desde el primer pago
