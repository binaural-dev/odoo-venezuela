## ADDED Requirements

### Requirement: Envío secuencial de líneas crudas sin transformación
`TfhkaDriver.printRawLines(lines)` SHALL enviar cada elemento del arreglo
`lines` como un comando independiente al protocolo TFHKA, respetando el
orden recibido y sin modificar su contenido, replicando el comportamiento
de la acción `logger_multi` del driver IoT legado (que llama `SendCmd(line)`
por cada línea, tal cual).

#### Scenario: Impresora no conectada
- **GIVEN** `this.isConnected` es `false`
- **WHEN** se llama `printRawLines(lines)`
- **THEN** retorna `{ success: false, error: "Impresora no conectada" }` sin
  intentar leer estado ni enviar ningún comando

#### Scenario: Entrada inválida
- **GIVEN** la impresora está conectada
- **WHEN** se llama `printRawLines(lines)` con `lines` que no es un arreglo o
  es un arreglo vacío
- **THEN** retorna `{ success: false, error: "No hay líneas para imprimir" }`
  sin enviar ningún comando

#### Scenario: Impresión exitosa de varias líneas
- **GIVEN** la impresora está conectada y en reposo (STS1 de espera)
- **WHEN** se llama `printRawLines(["800REPORTE DE VENTAS", "810"])`
- **THEN** cada línea se envía en orden como comando independiente vía
  `sendCommand(line, null, false, i > 0)` y el método retorna
  `{ success: true, error: "" }`

### Requirement: Recuperación ante impresora ocupada o comando fallido
`TfhkaDriver.printRawLines(lines)` SHALL verificar el estado de la impresora
antes de enviar la primera línea y SHALL abortar la transacción abierta
cuando la impresora no esté en reposo o cuando un comando individual falle,
para no dejar la impresora en un estado intermedio sin reportarlo.

#### Scenario: Impresora no está en reposo pero el abort tiene éxito
- **GIVEN** `getStatus()` reporta un STS1 que no es de espera
  (`_isWaitingState` retorna `false`)
- **WHEN** se llama `printRawLines(lines)`
- **THEN** se llama `abortTransaction()`; si retorna `true`, la impresión
  continúa normalmente con la primera línea

#### Scenario: Impresora no está en reposo y el abort falla
- **GIVEN** `getStatus()` reporta un STS1 que no es de espera
- **WHEN** se llama `printRawLines(lines)` y `abortTransaction()` retorna
  `false`
- **THEN** retorna `{ success: false, error: "La impresora tiene una
  transacción previa abierta (STS1=...). Reiníciala." }` sin enviar ninguna
  línea

#### Scenario: Un comando de la secuencia falla
- **GIVEN** la impresora está en reposo y se están enviando las líneas de
  `lines` en orden
- **WHEN** `sendCommand()` de una línea retorna `{ success: false, ... }`
- **THEN** se llama `abortTransaction()` y se retorna `{ success: false,
  error: "Error en línea [<line>]: <error>" }` sin enviar el resto de las
  líneas
