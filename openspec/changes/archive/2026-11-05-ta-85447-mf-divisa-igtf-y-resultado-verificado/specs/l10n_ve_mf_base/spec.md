## ADDED Requirements

### Requirement: Resultado verificado del documento fiscal

`printInvoice`, `printCreditNote` y `printDebitNote` DEBEN (MUST) tomar una foto de S1 (número, subtotal de ventas, Z y serial) antes de abrir el documento, si la máquina está en reposo. Un éxito NO DEBE (MUST NOT) cambiar. Si la impresión falla después de enviar un pago, DEBEN (MUST) consultar a la máquina y devolver `printed: true` con el número, `printed: false` (no emitido o anulado) o `printed: null` con la verificación.

#### Scenario: Factura exitosa

- **WHEN** la factura se imprime sin errores
- **THEN** el resultado es el mismo de siempre, sin `printed`, y la única diferencia en la secuencia es la lectura S1 previa

#### Scenario: Pago registrado reportado como fallido

- **GIVEN** que un comando falla después del primer pago y el driver manda `7`
- **WHEN** S1 muestra el número siguiente y el subtotal de ventas aumentó
- **THEN** el resultado es `success: true, printed: true, recovered: true` con ese número

#### Scenario: Máquina en reposo sin foto

- **WHEN** la máquina no está en reposo al empezar o S1 no responde
- **THEN** no hay foto y el resultado es el de siempre

### Requirement: Falla antes de enviar pagos

Si la impresión falla sin haber enviado ningún pago (comandos `2XX…`, `1XX` o `199`), el driver DEBE (MUST) devolver `printed: false` sin consultar nada más: sin pagos el documento no pudo quedar comprometido.

#### Scenario: Falla antes del primer pago

- **WHEN** un ítem falla y la máquina anula el documento
- **THEN** el resultado es `success: false, printed: false`, aunque el número haya avanzado, y no se lee S1 después de la falla

#### Scenario: Nota de crédito anulada antes de pagar

- **WHEN** una nota de crédito falla antes de enviar pagos
- **THEN** el resultado es `printed: false`

### Requirement: Contadores contradictorios

Si la máquina aceptó el `199` (cierre) y S1 no muestra el documento, el driver NO DEBE (MUST NOT) responder `printed: false`: DEBE (MUST) devolver `printed: null`, porque un "no impreso" equivocado lleva a reimprimir.

#### Scenario: Cierre aceptado sin cambio en los contadores

- **GIVEN** que la máquina aceptó el `199`
- **WHEN** S1 muestra el mismo número, o el número siguiente con el mismo subtotal de ventas
- **THEN** el resultado es `printed: null` con `reason: "unattributable"`

### Requirement: Verificación posterior de un documento sin confirmar

`verifyDocument(verification)` DEBE (MUST) resolver un resultado `printed: null` comparando S1 con la foto guardada; si el documento sigue abierto, lo termina con `7`. Si no se había enviado ningún pago, DEBE (MUST) devolver `printed: false`.

#### Scenario: La máquina responde de nuevo

- **GIVEN** un documento sin confirmar porque la máquina dejó de responder tras el cierre
- **WHEN** se verifica y S1 muestra el número siguiente con el subtotal aumentado
- **THEN** el resultado es `printed: true` con ese número

#### Scenario: Sin pagos enviados

- **GIVEN** una verificación con `paymentSent: false`
- **WHEN** S1 muestra el número siguiente con el subtotal aumentado (otro documento)
- **THEN** el resultado es `printed: false`

### Requirement: Motivo de un resultado desconocido

Un `printed: null` DEBE (MUST) traer `reason`: `no_response` si la máquina no respondió el estado o S1 (en `verifyDocument`, tras 3 consultas de estado), `other_printer` si el serial de S1 no es el de la foto (se mira antes que el número), y `unattributable` si el número avanzó más de uno, los contadores no cuadran o S1 respondió sin el contador del documento.

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

### Requirement: Reporte Z de un documento verificado tarde

Si la verificación concluye `printed: true`, el Reporte Z del resultado DEBE (MUST) ser el contador Z de la foto más uno, aunque se haya hecho un cierre Z antes de verificar.

#### Scenario: Verificación después de un cierre Z

- **GIVEN** una foto con el contador Z 137
- **WHEN** se verifica después de un Z (S1 con 138) y el documento quedó emitido
- **THEN** el resultado trae `reportZ = 138`

## MODIFIED Requirements

### Requirement: Identificación fiscal tras imprimir

Tras el `199` final, el driver DEBE (MUST) leer `S1` y devolver en la respuesta el número fiscal del documento (`lastInvoiceNumber`, `lastNCNumber` o `lastDebtNoteNumber` según el tipo), el serial de la máquina (`registeredMachineNumber`) y `reportZ = dailyClosureCounter + 1`. Si el S1 no se puede leer, el resultado DEBE (MUST) decidirse con la máquina (ver "Resultado verificado del documento fiscal").

#### Scenario: Lectura exitosa del S1

- **WHEN** la factura se imprime y el S1 responde con contadores válidos
- **THEN** la respuesta incluye `invoiceNumber`, `serial` y `reportZ` igual al contador de cierres diarios más uno

#### Scenario: S1 ilegible tras imprimir

- **WHEN** el S1 falla después del `199` y luego la máquina responde
- **THEN** el resultado es `success: true, printed: true, recovered: true` con el número emitido; si la máquina no vuelve a responder, es `printed: null` con la verificación

### Requirement: Impresión de nota de crédito

`printCreditNote(orderData)` DEBE (MUST) rechazar la operación si `invoice_affected` no trae `number`, `date` y `serial_machine`, y enviar la secuencia con los datos de la factura afectada: `iF*` con el número fiscal rellenado a 8 dígitos, `iI*` con el serial de la máquina e `iD*` con la fecha, usando para los ítems el prefijo `d` + código fiscal numérico (el código se envía crudo, sin el mapeo a caracteres `!`/`"`/`#` de la factura y sin quitar un eventual prefijo `t`). El monto del comando de descuento `q-<monto>` que se envía tras el subtotal DEBE (MUST) ser la suma de `|global_discount_amount|` de la orden más el valor absoluto de los precios de las líneas negativas, y solo se emite si esa suma es mayor que cero. El número resultante se toma de `lastNCNumber` del S1.

#### Scenario: NC sin factura afectada

- **WHEN** falta el número, la fecha o el serial de la factura afectada
- **THEN** devuelve `success: false` sin abrir ningún documento (solo se envía la lectura S1 previa, que no imprime)

#### Scenario: NC válida

- **WHEN** la NC trae la factura afectada completa y líneas válidas
- **THEN** la secuencia incluye `iF*`, `iI*`, `iD*`, ítems con prefijo `d` y el resultado trae el número de NC leído del S1

#### Scenario: NC con descuento global y línea negativa

- **WHEN** la orden trae `global_discount_amount = 100` y una línea con `price_unit = -40`
- **THEN** la línea negativa se excluye de los ítems y el comando enviado tras el subtotal es `q-` con 140
