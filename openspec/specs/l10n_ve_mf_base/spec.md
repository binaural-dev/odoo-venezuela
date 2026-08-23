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

`getStatus()` del driver DEBE (MUST) enviar el byte ENQ (`0x05`) y parsear la respuesta de 5 bytes `STX|STS1|STS2|ETX|LRC`, validando que `LRC = STS1 ^ STS2 ^ ETX` (`FiscalProtocol.parseStatusENQ`). El parseo (`StatusParser`) interpreta STS2 por códigos exactos: `0x40` = sin errores, `0x41/0x42/0x43` = errores de papel/mecánicos, `0x50`-`0x6C` = errores generales (comando inválido, tasa inválida, error fiscal, memoria fiscal llena, etc.), y expone `errors` (lista legible), `isOperational` y `statusText`.

#### Scenario: Impresora sin errores

- **WHEN** la respuesta al ENQ trae STS2 = `0x40` y LRC correcto
- **THEN** el estado parseado tiene `errors` vacío

#### Scenario: LRC de ENQ inválido

- **WHEN** el LRC de la respuesta ENQ no coincide con `STS1 ^ STS2 ^ ETX`
- **THEN** `parseStatusENQ` devuelve `null` y `getStatus()` reporta fallo

### Requirement: Chequeo de estado y recuperación de transacción antes de cada comando

`sendCommand` DEBE (MUST), salvo para los comandos exentos `9`, `199` y `w` (o cuando se pasa `checkStatus = false`), consultar el estado vía ENQ antes de enviar: si la impresora reporta errores el comando se rechaza con el detalle, y si STS1 indica transacción en curso (`0x41/0x61/0x65/0x62/0x42`) se intenta `abortTransaction()` — que envía "9" (anular documento) y como respaldo "199" (fin de documento) hasta que STS1 vuelva a un estado de espera (`0x40/0x60/0x64`) — rechazando el comando si el aborto falla.

#### Scenario: Impresora con error activo

- **WHEN** el ENQ previo reporta errores (por ejemplo sin papel)
- **THEN** el comando no se envía y el resultado es `success: false` con los errores concatenados

#### Scenario: Transacción previa abierta recuperable

- **WHEN** STS1 indica transacción en curso y el comando "9" es aceptado (ACK)
- **THEN** la transacción previa se anula y el comando original continúa

#### Scenario: Transacción previa no recuperable

- **WHEN** ni "9" ni "199" logran devolver la impresora a estado de espera
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

El driver DEBE (MUST) formatear precios, cantidades y montos de pago con dígitos crudos rellenados con ceros (`_formatAmount`) según la configuración del flag 21 de la orden: `00` = 8+2 enteros/decimales de monto (5+3 cantidad, 10+2 pago), `01` = 7+3, `02` = 6+4 y `30` = 14+2 (14+3 cantidad, 15+2 pago); un valor desconocido o ausente usa `00`.

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

El driver DEBE (MUST) clasificar los códigos de método de pago 20-24 como pago en divisas (`_isDivisaPaymentMethod`) y, cuando la orden contiene al menos uno (`_hasDivisaPayment`), enviar TODOS los pagos como comandos `2XX` individuales — sin agrupar por método, un comando por pago — y NO enviar ningún cierre directo `1XX`, dejando que el `199` final cierre el documento para que la impresora calcule el IGTF (secuencia obligatoria del manual IGTF TFHKA con Flag 50=01). Antes de la fase de pagos se lee `S25` para diagnóstico del desglose IGTF del documento en curso.

#### Scenario: Pago mixto nacional + divisa

- **WHEN** la orden tiene un pago con código 01 y otro con código 20
- **THEN** se envían dos comandos `2XX` (uno por pago) y ningún `1XX`; el cierre lo hace el `199`

#### Scenario: Dos pagos con el mismo método en divisa

- **WHEN** la orden tiene dos pagos con código 22
- **THEN** se envían dos comandos `222...` separados, sin sumar los montos

### Requirement: Impresión de nota de crédito

`printCreditNote(orderData)` DEBE (MUST) rechazar la operación si `invoice_affected` no trae `number`, `date` y `serial_machine`, y enviar la secuencia con los datos de la factura afectada: `iF*` con el número fiscal rellenado a 8 dígitos, `iI*` con el serial de la máquina e `iD*` con la fecha, usando para los ítems el prefijo `d` + código fiscal numérico. Las líneas con precio negativo se acumulan como descuento global y se envían tras el subtotal como comando `q-<monto>`. El número resultante se toma de `lastNCNumber` del S1.

#### Scenario: NC sin factura afectada

- **WHEN** falta el número, la fecha o el serial de la factura afectada
- **THEN** devuelve `success: false` sin enviar ningún comando

#### Scenario: NC válida

- **WHEN** la NC trae la factura afectada completa y líneas válidas
- **THEN** la secuencia incluye `iF*`, `iI*`, `iD*`, ítems con prefijo `d` y el resultado trae el número de NC leído del S1

### Requirement: Impresión de nota de débito

`printDebitNote(orderData)` DEBE (MUST) aplicar las mismas validaciones de factura afectada que la NC (`number`, `date`, `serial_machine` obligatorios, `iF*`/`iI*`/`iD*`) pero usando para los ítems el prefijo backtick (`` ` ``) + código fiscal, tomando el número resultante de `lastDebtNoteNumber` del S1.

#### Scenario: ND válida

- **WHEN** se imprime una ND con factura afectada completa
- **THEN** los ítems se envían con prefijo backtick y el resultado trae el número de ND del S1

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

El driver DEBE (MUST) exponer lecturas parseadas de estados de la impresora: `readS3Data()` devuelve las tres tasas de impuesto, el bloque `igtf` (tipo, etiqueta y tasa, tomados de la cuarta línea) y los `systemFlags` crudos; `readS4Data()` devuelve los medios de pago programados como `{code, name}` (código = 2 primeros dígitos de cada línea); `readS25Data()` devuelve el desglose IGTF del documento fiscal en curso (bases, impuesto, total con y sin IGTF, contadores y tipo de documento) calculando `igtfAmount` como la diferencia entre el total con IGTF y el total sin IGTF. Los montos usan 2 decimales implícitos.

#### Scenario: Tasa IGTF programada

- **WHEN** se invoca `readS3Data()` en una impresora con IGTF al 3%
- **THEN** `data.igtf.value` es `3.00` y `systemFlags` contiene los flags crudos del S3

#### Scenario: S25 sin transacción abierta

- **WHEN** se invoca `readS25Data()` sin documento fiscal abierto
- **THEN** los montos parseados son cero y `documentType` es `"0"` (Ninguno)

### Requirement: Formato de montos para líneas informativas

`_formatDisplayAmount(value)` DEBE (MUST) formatear montos con convención venezolana — punto como separador de miles y coma decimal con 2 decimales (39290.94 → `"39.290,94"`) — y usarse únicamente en texto de líneas informativas `iXX` impresas en el ticket, nunca en los campos de dígitos crudos del protocolo (ítems y pagos `2XX`, que usan `_formatAmount`).

#### Scenario: Monto menor a mil

- **WHEN** se formatea `15`
- **THEN** devuelve `"15,00"` sin separador de miles

### Requirement: Línea informativa de descuento global en factura

Cuando la orden trae `global_discount_rate > 0` y `global_discount_amount > 0`, la fase de pie de la factura DEBE (MUST) emitir una línea informativa `iNN` con el texto `DESC. GLOBAL = <monto formateado>`, respetando el cupo de 10 líneas informativas (si no hay slot libre no se emite), y una segunda línea `DESC. GLOBAL EXCEDIO SUBTOTAL` cuando `global_clamped` es verdadero y queda cupo.

#### Scenario: Descuento global normal

- **WHEN** la orden trae un descuento global de 39290.94 Bs
- **THEN** el pie incluye la línea `DESC. GLOBAL = 39.290,94`

#### Scenario: Descuento clampeado

- **WHEN** `global_clamped` es verdadero
- **THEN** se emite además la línea `DESC. GLOBAL EXCEDIO SUBTOTAL`

### Requirement: Reportes fiscales y gaveta

El driver DEBE (MUST) exponer `printReportX()` (comando `I0X`, consulta sin cerrar el día), `printReportZ()` (comando `I0Z`, cierre fiscal del día) y `openDrawer()` (comando `0`, apertura de gaveta), y en la fase de pagos enviar el comando `w` (abrir gaveta) cuando la orden trae `has_cashbox`.

#### Scenario: Reporte Z

- **WHEN** se invoca `printReportZ()` con la impresora conectada y en reposo
- **THEN** se envía `I0Z` con timeout de reporte

#### Scenario: Orden con gaveta

- **WHEN** la orden trae `has_cashbox = true`
- **THEN** el comando `w` se envía antes de los comandos de pago
