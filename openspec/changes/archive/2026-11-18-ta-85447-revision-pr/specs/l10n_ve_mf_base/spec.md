## MODIFIED Requirements

### Requirement: Verificación posterior de un documento sin confirmar

`verifyDocument(verification)` DEBE (MUST) resolver un `printed: null` comparando S1 con la foto; si el documento sigue abierto, lo termina con `7`. Sin pagos enviados (`paymentSent: false`) DEBE (MUST) devolver `printed: false`. Una verificación dañada (sin foto, sin `paymentSent` o `closeAcked` booleanos, o con un `docType` desconocido) DEBE (MUST) ir a revisión manual (`unattributable`) sin consultar la máquina.

#### Scenario: La máquina responde de nuevo

- **GIVEN** un documento sin confirmar porque la máquina dejó de responder tras el cierre
- **WHEN** se verifica y S1 muestra el número siguiente con el subtotal aumentado
- **THEN** el resultado es `printed: true` con ese número

#### Scenario: Sin pagos enviados

- **GIVEN** una verificación con `paymentSent: false`
- **WHEN** S1 muestra el número siguiente con el subtotal aumentado (otro documento)
- **THEN** el resultado es `printed: false`

#### Scenario: Verificación dañada

- **WHEN** se verifica con `null`, sin foto, sin `paymentSent` o `closeAcked`, o con un `docType` desconocido
- **THEN** el resultado es `printed: null` con `reason: "unattributable"` y no se envía nada a la máquina

### Requirement: Motivo de un resultado desconocido

Un `printed: null` DEBE (MUST) traer `reason`: `no_response` si la máquina no respondió el estado o S1 (en `verifyDocument`, tras 3 consultas de estado); `document_open` si una nota de crédito o de débito sigue abierta después de que el `7` no la pudo terminar; `other_printer` si el serial de S1 no es el de la foto (se mira antes que el número); y `unattributable` si el número avanzó más de uno, los contadores no cuadran o S1 respondió sin el contador del documento.

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

#### Scenario: Factura abierta después del 7

- **WHEN** lo mismo pasa con una factura
- **THEN** se compara S1 como siempre: está medido que S1 ya cuenta la factura desde el primer pago
