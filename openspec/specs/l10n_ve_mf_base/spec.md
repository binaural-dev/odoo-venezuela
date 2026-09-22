# l10n_ve_mf_base

## Purpose

Base compartida (frontend JavaScript) para la integración de impresoras fiscales The Factory HKA (TFHKA) vía Web Serial API, sin IoT Box. Provee la capa de transporte (`SerialConnection`), la capa de protocolo (`FiscalProtocol` + `StatusParser`) y el driver de alto nivel (`TfhkaDriver`) con los comandos de facturación, notas de crédito/débito, reportes, reimpresión y consultas de datos. No define modelos Odoo: solo assets en `web.assets_backend`. Depende de `web`; lo consumen `l10n_ve_account_mf` (backend de Facturación) y `l10n_ve_pos_mf` (POS).

## Requirements

### Requirement: Transporte serial con configuración TFHKA

La clase `SerialConnection` DEBE (MUST) abrir el puerto serial con la configuración RS-232 requerida por TFHKA: 9600 baudios, 8 bits de datos, 1 bit de parada y paridad par (`parity: "even"`). `requestPort()` dispara el prompt de selección de puerto del navegador (requiere gesto del usuario) y `autoConnect()` reconecta en silencio al primer puerto ya autorizado (`navigator.serial.getPorts()`), sin prompt.

#### Scenario: Reconexión silenciosa

- **WHEN** se invoca `autoConnect()` y existe al menos un puerto serial previamente autorizado por el usuario
- **THEN** se abre ese puerto con la configuración 9600 8E1 y la conexión queda establecida sin interacción del usuario

#### Scenario: Sin puerto autorizado

- **WHEN** se invoca `autoConnect()` y no hay puertos autorizados, o el navegador no soporta Web Serial (`navigator.serial` ausente)
- **THEN** devuelve `false` sin lanzar el prompt de selección

### Requirement: Lectura serial con detección de ACK/NAK y liberación de locks

El método `read(timeout, delimiter)` de `SerialConnection` DEBE (MUST) acumular bytes hasta recibir un byte único ACK (`0x06`) o NAK (`0x15`), encontrar el delimitador ETX (`0x03`) o agotar el timeout (devuelve `null`), y DEBE (MUST) liberar siempre el lock de lectura (`readLock`) en el bloque `finally`. Escrituras y lecturas están serializadas con `writeLock`/`readLock` para evitar colisiones.

#### Scenario: Respuesta con delimitador

- **WHEN** la impresora responde una trama que contiene ETX antes del timeout
- **THEN** `read` devuelve todos los bytes acumulados

#### Scenario: Timeout de lectura

- **WHEN** no llega ACK, NAK ni ETX dentro del timeout
- **THEN** `read` devuelve `null` y el `readLock` queda liberado para la siguiente operación

### Requirement: Construcción y validación de tramas TFHKA

`FiscalProtocol.buildFrame(command)` DEBE (MUST) construir la trama binaria `STX(0x02) + comando + ETX(0x03) + LRC`, donde el LRC es el XOR de los bytes del comando más el ETX (sin incluir el STX). `parseResponse(response)` DEBE (MUST) validar que la respuesta comience con STX, contenga ETX y que el LRC recibido coincida con el calculado sobre `DATA + ETX`; si no coincide devuelve `valid: false` con el error.

#### Scenario: Trama de envío

- **WHEN** se construye la trama para un comando ASCII
- **THEN** el último byte es el XOR de todos los bytes del comando y del ETX, y el primer byte es STX

#### Scenario: Respuesta con LRC inválido

- **WHEN** llega una respuesta cuyo byte de LRC no coincide con el XOR calculado
- **THEN** `parseResponse` devuelve `valid: false` indicando LRC inválido y los datos no se usan

### Requirement: Consulta de estado ENQ

`getStatus()` del driver DEBE (MUST) enviar el byte ENQ (`0x05`) y parsear la respuesta de 5 bytes `STX|STS1|STS2|ETX|LRC`, validando que `LRC = STS1 ^ STS2 ^ ETX` (`FiscalProtocol.parseStatusENQ`); STX y ETX inválidos solo se registran en consola y no invalidan el parseo. `StatusParser` interpreta STS2 por códigos exactos y expone `raw` (`sts1`/`sts2`), `errorFlags`, `errors`, `isOperational`, `hasErrors` (verdadero para cualquier STS2 distinto de `0x40`) y `statusText`.

#### Scenario: Impresora sin errores

- **WHEN** la respuesta al ENQ trae STS2 = `0x40`, STS1 sin los bits `0x08`/`0x10` y LRC correcto
- **THEN** el estado parseado tiene `errors` vacío

#### Scenario: LRC de ENQ inválido

- **WHEN** el LRC de la respuesta ENQ no coincide con `STS1 ^ STS2 ^ ETX`
- **THEN** `parseStatusENQ` devuelve `null` y `getStatus()` reporta fallo

### Requirement: Cobertura parcial de la lista legible de errores

`StatusParser.getErrorList(sts1, sts2)` DEBE (MUST) devolver texto solo para los códigos que reconoce explícitamente: memoria fiscal llena (`0x6C`), error en memoria fiscal (`0x64`), error fiscal (`0x60`), papel (`0x41`/`0x42`/`0x43`), gaveta (cualquier STS2 con el bit `0x08` encendido) y los avisos de memoria de STS1 (bits `0x08`/`0x10`). Los códigos de error de comando/valor (`0x50` valor inválido, `0x54` tasa inválida, `0x58` sin directivas, `0x5C` comando inválido) NO producen entradas propias en `errors`: `0x50` y `0x54` devuelven lista vacía y `0x58`/`0x5C` solo reportan "Gaveta abierta o con fallo" por el bit `0x08`, aunque `hasErrors()` sea verdadero, `statusText` los nombre y `errorFlags.printerGeneralError` (`sts2 >= 0x50`) esté activo.

#### Scenario: Tasa inválida no aparece en errors

- **WHEN** la respuesta al ENQ trae STS2 = `0x54` (tasa inválida)
- **THEN** `errors` queda vacío, `statusText` es "Tasa Inválida" y `hasErrors()` es verdadero

#### Scenario: Comando inválido reportado como gaveta

- **WHEN** la respuesta al ENQ trae STS2 = `0x5C` (comando inválido)
- **THEN** el único texto en `errors` es el de gaveta, derivado del bit `0x08`

### Requirement: Chequeo de estado y recuperación de transacción antes de cada comando

`sendCommand` DEBE (MUST), salvo para los comandos exentos `9`, `199` y `w` (o cuando se pasa `checkStatus = false`), consultar el estado vía ENQ antes de enviar: el rechazo se decide únicamente por `status.errors` (la lista legible de `StatusParser`, no por `isOperational` ni `hasErrors`), y si STS1 indica transacción en curso (`0x41/0x61/0x65/0x62/0x42`) se intenta `abortTransaction()`, rechazando el comando si el aborto falla. Un STS1 que no sea de espera (`0x40/0x60/0x64`) ni de transacción solo genera una advertencia en consola y el comando se envía igual. `abortTransaction()` envía "9" (anular documento) y, si "9" no devuelve ACK ni deja la impresora en espera, "199" (fin de documento); DEBE (MUST) devolver verdadero en cuanto "9" o "199" reciben ACK, sin re-verificar STS1 en ese camino.

Las tres rutinas de impresión (`printInvoice`, `printCreditNote`, `printDebitNote`) invocan cada comando de la secuencia con `checkStatus = false`, por lo que este chequeo NO ocurre comando a comando durante la impresión: el gate de estado del documento es la lectura de estado propia de cada rutina antes de la fase 1.

#### Scenario: Impresora con error activo

- **WHEN** el ENQ previo devuelve `errors` no vacío (por ejemplo sin papel)
- **THEN** el comando no se envía y el resultado es `success: false` con los errores concatenados

#### Scenario: Error de STS2 fuera de la lista legible

- **WHEN** el ENQ previo devuelve STS2 = `0x54` (tasa inválida), cuyo `errors` es vacío
- **THEN** `sendCommand` no rechaza el comando y lo envía a la impresora

#### Scenario: Transacción previa abierta recuperable

- **WHEN** STS1 indica transacción en curso y el comando "9" es aceptado (ACK)
- **THEN** `abortTransaction()` devuelve verdadero y el comando original continúa

#### Scenario: Transacción previa no recuperable

- **WHEN** ni "9" ni "199" reciben ACK y el STS1 posterior sigue sin ser de espera
- **THEN** el comando falla indicando que la impresora está ocupada y debe reiniciarse

### Requirement: Timeouts automáticos por tipo de comando y reintentos ante NAK

Cuando no se pasa timeout explícito, `sendCommand` DEBE (MUST) asignarlo según el comando: 60s para programación (`PJ...`), 30s para reportes (`I0X`/`I0Z`), 15s para cierres (`101`, `199`, `3`) y 5s para el resto. Ante NAK DEBE (MUST) reintentar hasta 3 intentos con 500ms de espera. Los comandos pesados (`101`, `199`, `3` y los de pago `2XX`) insertan un delay de 500ms entre escritura y lectura; los demás 100ms.

#### Scenario: Comando de reporte sin timeout explícito

- **WHEN** se envía `I0Z` sin timeout
- **THEN** el driver espera la respuesta hasta 30 segundos

#### Scenario: NAK persistente

- **WHEN** la impresora responde NAK en los 3 intentos
- **THEN** el resultado es `success: false` con "Máximo de reintentos alcanzado"

### Requirement: Formato numérico según Flag 21

El driver DEBE (MUST) formatear precios, cantidades y montos de pago con dígitos crudos rellenados con ceros (`_formatAmount`) según la configuración del flag 21 de la orden: `00` = 8+2 enteros/decimales de monto (5+3 cantidad, 10+2 pago, 7+2 descuento), `01` = 7+3, `02` = 6+4 y `30` = 14+2 (14+3 cantidad, 15+2 pago, 15+2 descuento); las configuraciones `00`, `01` y `02` comparten cantidad 5+3, pago 10+2 y descuento 7+2. Un valor desconocido o ausente usa `00`. La tabla está duplicada en `printInvoice`, `printCreditNote` y `printDebitNote`; solo `printInvoice` acepta un segundo argumento `flag21Config` que, cuando se pasa, DEBE (MUST) tener prioridad sobre `flag_21` de la orden.

#### Scenario: Flag 30 para montos grandes

- **WHEN** la orden trae `flag_21 = "30"` y una línea con precio 100.50
- **THEN** el precio se codifica con 14 dígitos enteros y 2 decimales (`00000000000100` + `50`)

#### Scenario: Flag desconocido

- **WHEN** la orden trae un `flag_21` que no es 00/01/02/30
- **THEN** se aplica la configuración estándar `00`

### Requirement: Impresión de factura fiscal

`printInvoice(orderData)` DEBE (MUST) verificar que la impresora esté en reposo (abortando una transacción previa si es necesario) y enviar la secuencia completa: RIF del cliente (`iR*`), razón social (`iS*`, con word-wrap a 40 caracteres cuyas líneas de continuación van como informativas `iNN`, máximo 10), dirección/teléfono y líneas de encabezado como informativas, un comando de ítem por línea con precio positivo — carácter de impuesto + precio + cantidad + código opcional `|code|` + descripción (Ñ→N, truncada a 127 caracteres) —, subtotal (`3`), comandos de pago, líneas de pie y el cierre `199`. Las líneas con `price_unit <= 0` se excluyen de los ítems. Si un comando falla (excepto `1XX`), se aborta la transacción y se devuelve el error.

#### Scenario: Factura con cliente y varias líneas

- **WHEN** se imprime una orden con partner, líneas y pagos válidos
- **THEN** la secuencia enviada inicia con `iR*<vat>` e `iS*<nombre>`, incluye un comando por ítem con su carácter de impuesto y termina con `199`

#### Scenario: Fallo a mitad de secuencia

- **WHEN** un comando de la fase de apertura es rechazado por la impresora
- **THEN** el driver invoca `abortTransaction()` y devuelve `success: false` con el comando que falló

### Requirement: Mapeo del código fiscal de impuesto al carácter TFHKA

El driver DEBE (MUST) mapear el código fiscal de la línea al carácter de ítem del protocolo: `0` → espacio (exento), `1` → `!` (tasa general), `2` → `"` (tasa reducida), `3` → `#` (tasa adicional); un código desconocido usa `!` y un prefijo `t` se elimina antes de mapear.

#### Scenario: Línea exenta

- **WHEN** una línea tiene `fiscal_code = "0"`
- **THEN** el comando de ítem comienza con el carácter espacio (0x20)

### Requirement: Cierre multipago en moneda nacional

Cuando ningún pago es en divisas (códigos 01-19), `_appendPaymentCommands` DEBE (MUST) agrupar los pagos por método sumando montos, enviar `2<método><monto>` para cada método excepto el de mayor monto, y cerrar con `1<método>` usando el método de mayor monto. Sin pagos (o todos en cero) se envía `101` (cierre en efectivo). Un fallo en un comando `1XX` no es fatal: la secuencia continúa y el `199` final cierra el documento.

#### Scenario: Dos métodos nacionales

- **WHEN** la orden tiene pagos 01 por 30 Bs y 06 por 70 Bs
- **THEN** se envía `201...` con 30 y el cierre es `106`

#### Scenario: Orden sin pagos

- **WHEN** `payment_lines` está vacío
- **THEN** se envía `101`

#### Scenario: Fallo del cierre directo

- **WHEN** el comando `1XX` devuelve error
- **THEN** la impresión continúa y el documento se cierra con el `199` final

### Requirement: Cierre vía 199 con pagos en divisas (IGTF)

El driver DEBE (MUST) clasificar los códigos de método de pago 20-24 como pago en divisas (`_isDivisaPaymentMethod`) y, cuando la orden contiene al menos uno (`_hasDivisaPayment`), enviar TODOS los pagos como comandos `2XX` individuales — sin agrupar por método, un comando por pago, omitiendo los de monto cero o negativo — y NO enviar ningún cierre directo `1XX`, dejando que el `199` final cierre el documento para que la impresora calcule el IGTF (secuencia obligatoria del manual IGTF TFHKA con Flag 50=01).

Los montos `2XX` se envían tal como los trae la orden: cuando hay pago en divisas, tras la fase 1 se lee `S25` únicamente para registrar el desglose en consola y su resultado se descarta — el driver NO suma el IGTF calculado por la impresora a ningún pago (`_adjustPaymentsWithIGTF` existe pero ninguna ruta lo invoca). Si la lectura del `S25` falla, la impresión continúa. Por lo tanto, cuando el IGTF hace que el total esperado por la impresora supere la suma de los `2XX` enviados, el `199` es rechazado con NAK y el documento no se cierra.

#### Scenario: Pago mixto nacional + divisa

- **WHEN** la orden tiene un pago con código 01 y otro con código 20
- **THEN** se envían dos comandos `2XX` (uno por pago) y ningún `1XX`; el cierre lo hace el `199`

#### Scenario: Dos pagos con el mismo método en divisa

- **WHEN** la orden tiene dos pagos con código 22
- **THEN** se envían dos comandos `222...` separados, sin sumar los montos

#### Scenario: IGTF leído pero no aplicado

- **WHEN** el `S25` devuelve un `igtfAmount` mayor que cero para el documento en curso
- **THEN** los comandos `2XX` conservan los montos originales de la orden y el monto del IGTF no se suma a ningún pago

### Requirement: Impresión de nota de crédito

`printCreditNote(orderData)` DEBE (MUST) rechazar la operación si `invoice_affected` no trae `number`, `date` y `serial_machine`, y enviar la secuencia con los datos de la factura afectada: `iF*` con el número fiscal rellenado a 8 dígitos, `iI*` con el serial de la máquina e `iD*` con la fecha, usando para los ítems el prefijo `d` + código fiscal numérico (el código se envía crudo, sin el mapeo a caracteres `!`/`"`/`#` de la factura y sin quitar un eventual prefijo `t`). El monto del comando de descuento `q-<monto>` que se envía tras el subtotal DEBE (MUST) ser la suma de `|global_discount_amount|` de la orden más el valor absoluto de los precios de las líneas negativas, y solo se emite si esa suma es mayor que cero. El número resultante se toma de `lastNCNumber` del S1.

#### Scenario: NC sin factura afectada

- **WHEN** falta el número, la fecha o el serial de la factura afectada
- **THEN** devuelve `success: false` sin enviar ningún comando

#### Scenario: NC válida

- **WHEN** la NC trae la factura afectada completa y líneas válidas
- **THEN** la secuencia incluye `iF*`, `iI*`, `iD*`, ítems con prefijo `d` y el resultado trae el número de NC leído del S1

#### Scenario: NC con descuento global y línea negativa

- **WHEN** la orden trae `global_discount_amount = 100` y una línea con `price_unit = -40`
- **THEN** la línea negativa se excluye de los ítems y el comando enviado tras el subtotal es `q-` con 140

### Requirement: Impresión de nota de débito

`printDebitNote(orderData)` DEBE (MUST) aplicar las mismas validaciones de factura afectada que la NC (`number`, `date`, `serial_machine` obligatorios, `iF*`/`iI*`/`iD*`) y el mismo tratamiento del descuento global (`q-` con `|global_discount_amount|` más los precios negativos), pero usando para los ítems el prefijo backtick (`` ` ``) + código fiscal, tomando el número resultante de `lastDebtNoteNumber` del S1.

#### Scenario: ND válida

- **WHEN** se imprime una ND con factura afectada completa
- **THEN** los ítems se envían con prefijo backtick y el resultado trae el número de ND del S1

#### Scenario: S1 en formato corto

- **WHEN** el S1 posterior al `199` devuelve 15 campos o menos (formato corto), en el que `_parseS1Data` no asigna `lastDebtNoteNumber`
- **THEN** la ND se reporta como `success: false` con "Nota de débito impresa, pero S1 no devolvió número de ND", aunque el documento ya se imprimió

### Requirement: Identificación fiscal tras imprimir

Tras el `199` final, el driver DEBE (MUST) leer `S1` y devolver en la respuesta el número fiscal del documento (`lastInvoiceNumber`, `lastNCNumber` o `lastDebtNoteNumber` según el tipo), el serial de la máquina (`registeredMachineNumber`) y `reportZ = dailyClosureCounter + 1` (el Z al que pertenecerá el documento). Si el S1 no se puede leer o no devuelve el número, el resultado es `success: false` indicando que el documento se imprimió pero sin datos fiscales.

#### Scenario: Lectura exitosa del S1

- **WHEN** la factura se imprime y el S1 responde con contadores válidos
- **THEN** la respuesta incluye `invoiceNumber`, `serial` y `reportZ` igual al contador de cierres diarios más uno

#### Scenario: S1 ilegible tras imprimir

- **WHEN** el S1 falla después del `199`
- **THEN** el resultado es `success: false` con un mensaje que aclara que el documento sí se imprimió

### Requirement: Reimpresión de documentos fiscales

`reprintDocument({type, number})` DEBE (MUST) mapear `out_invoice` → comando `RF` y `out_refund` → `RC`, construir el rango con el número fiscal limpiado a dígitos y rellenado a 7 posiciones (`<modo><n><n>`), y enviar el comando con timeout de 30 segundos. Tipos no soportados o números sin dígitos se rechazan con error.

#### Scenario: Reimpresión de factura

- **WHEN** se reimprime una factura con número fiscal `1234`
- **THEN** se envía `RF00012340001234` y se espera hasta 30 segundos

#### Scenario: Tipo no soportado

- **WHEN** se pasa un `type` distinto de `out_invoice`/`out_refund`
- **THEN** devuelve `success: false` sin enviar comandos

### Requirement: Consulta de modelo de máquina (SV)

`getMachineModel()` DEBE (MUST) enviar el comando `SV` y parsear la respuesta en `country` (últimos 2 caracteres), `modelCode` (resto) y `model` (nombre mapeado; `Z1F` → `SRP-812`, códigos no mapeados devuelven el propio código), devolviendo error si la impresora está desconectada o la respuesta tiene menos de 3 caracteres útiles.

#### Scenario: Respuesta SVZ1FVE

- **WHEN** la impresora responde `SVZ1FVE`
- **THEN** el resultado es `modelCode = "Z1F"`, `model = "SRP-812"`, `country = "VE"`

### Requirement: Lecturas de datos S3, S4 y S25

El driver DEBE (MUST) exponer lecturas parseadas de estados de la impresora: `readS3Data()` devuelve las tres tasas de impuesto, el bloque `igtf` (tipo, etiqueta y tasa, tomados de la cuarta línea) y los `systemFlags` crudos; `readS4Data()` devuelve los medios de pago programados como `{code, name}` (código = 2 primeros dígitos de cada línea, o cadena vacía si la línea no empieza con dos dígitos); `readS25Data()` devuelve el desglose IGTF del documento fiscal en curso (bases, impuesto, total con y sin IGTF, contadores y tipo de documento) calculando `igtfAmount` como la diferencia entre el total con IGTF y el total sin IGTF. Los montos usan 2 decimales implícitos y las tres lecturas se envían con `checkStatus = false`.

`_parseS25Data` DEBE (MUST) exigir al menos 6 campos (devuelve `null` con menos) y toma el tipo de documento del séptimo campo, quedando en `""` / "Desconocido" si no viene. El prefijo que elimina es `^S2` y no `^S25`, por lo que si la impresora ecoa el comando completo el dígito `5` sobrante queda como primer campo y el resto de los valores se lee desplazado una posición.

#### Scenario: Tasa IGTF programada

- **WHEN** se invoca `readS3Data()` en una impresora con IGTF al 3%
- **THEN** `data.igtf.value` es `3.00` y `systemFlags` contiene los flags crudos del S3

#### Scenario: S25 con menos de 6 campos

- **WHEN** la respuesta al `S25` trae menos de 6 campos útiles
- **THEN** `readS25Data()` devuelve `success: false` con el error de parseo

### Requirement: Formato de montos para líneas informativas

`_formatDisplayAmount(value)` DEBE (MUST) formatear montos con convención venezolana — punto como separador de miles y coma decimal con 2 decimales (39290.94 → `"39.290,94"`) — y usarse únicamente en texto de líneas informativas `iXX` impresas en el ticket, nunca en los campos de dígitos crudos del protocolo (ítems y pagos `2XX`, que usan `_formatAmount`).

#### Scenario: Monto menor a mil

- **WHEN** se formatea `15`
- **THEN** devuelve `"15,00"` sin separador de miles

### Requirement: Línea informativa de descuento global

Cuando la orden trae `global_discount_rate > 0` y `global_discount_amount > 0`, la fase de pie DEBE (MUST) emitir una línea informativa `iNN` con el texto `DESC. GLOBAL = <monto formateado>`, respetando el cupo de 10 líneas informativas (si no hay slot libre no se emite), y una segunda línea `DESC. GLOBAL EXCEDIO SUBTOTAL` cuando `global_clamped` es verdadero y queda cupo. `_appendFooterInfo` es el único punto de emisión y lo invocan las tres rutinas, así que la línea DEBE (MUST) emitirse también en notas de crédito y de débito (donde el mismo monto ya viaja además como comando `q-`). El contador de índices del pie arranca en `00` en cada documento, de modo que reutiliza los índices `iNN` ya usados por el encabezado.

#### Scenario: Descuento global normal

- **WHEN** la orden trae un descuento global de 39290.94 Bs
- **THEN** el pie incluye la línea `DESC. GLOBAL = 39.290,94`

#### Scenario: Descuento clampeado

- **WHEN** `global_clamped` es verdadero
- **THEN** se emite además la línea `DESC. GLOBAL EXCEDIO SUBTOTAL`

#### Scenario: Nota de crédito con descuento global

- **WHEN** se imprime una NC cuya orden trae `global_discount_rate > 0` y `global_discount_amount > 0`
- **THEN** el pie de la NC también incluye la línea `DESC. GLOBAL = <monto>`, además del comando `q-` enviado tras el subtotal

### Requirement: Reportes fiscales y gaveta

El driver DEBE (MUST) exponer `printReportX()` (comando `I0X`, consulta sin cerrar el día), `printReportZ()` (comando `I0Z`, cierre fiscal del día) y `openDrawer()` (comando `0`, apertura de gaveta), y en la fase de pagos enviar el comando `w` (abrir gaveta) cuando la orden trae `has_cashbox`.

#### Scenario: Reporte Z

- **WHEN** se invoca `printReportZ()` con la impresora conectada y en reposo
- **THEN** se envía `I0Z` con timeout de reporte

#### Scenario: Orden con gaveta

- **WHEN** la orden trae `has_cashbox = true`
- **THEN** el comando `w` se envía antes de los comandos de pago
