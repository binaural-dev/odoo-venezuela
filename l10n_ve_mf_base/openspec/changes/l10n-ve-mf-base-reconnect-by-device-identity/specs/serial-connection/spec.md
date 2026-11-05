## MODIFIED Requirements

### Requirement: Reconexión automática por identidad del dispositivo

`SerialConnection.autoConnect()` SHALL seleccionar el puerto a reabrir SOLO
por identidad USB (VID/PID) guardada, y no por posición en
`navigator.serial.getPorts()`. Cuando NO exista identidad guardada,
`autoConnect()` SHALL abstenerse (devolver `false`) sin abrir ningún puerto
—ni siquiera si hay uno solo—, para no adoptar/sondear/cerrar a ciegas otro
serial activo (p.ej. la balanza). La identidad SHALL persistirse únicamente
tras verificar con `getStatus()` que el puerto responde como máquina fiscal
(en `TfhkaDriver`), nunca en `requestPort()`/`autoConnect()` por sí solos.

#### Scenario: Varios seriales autorizados, reconexión a la máquina fiscal

- **GIVEN** la pestaña tiene autorizados el puerto de la máquina fiscal y
  el de la balanza, y la identidad de la MF está guardada
- **WHEN** se llama `autoConnect()`
- **THEN** se reabre el puerto cuya identidad USB coincide con la máquina
  fiscal, sin importar su posición en `getPorts()`

#### Scenario: Sin identidad guardada

- **GIVEN** no hay identidad de MF guardada (primer arranque tras el deploy)
- **WHEN** se llama `autoConnect()` (haya uno o varios puertos autorizados)
- **THEN** no se abre ningún puerto (devuelve `false`) y se registra un
  aviso pidiendo conectar la MF una vez desde el botón; recién ese
  `requestPort()`, verificado con `getStatus()`, fija la identidad

#### Scenario: La identidad no se guarda si el puerto no es una MF

- **GIVEN** se abrió un puerto (por adopción o selección) que no responde al
  comando de estado TFHKA (p.ej. la balanza)
- **WHEN** `getStatus()` devuelve null
- **THEN** NO se persiste identidad y el puerto se suelta
  (`connection.disconnect()`), dejándolo libre para su dueño real

### Requirement: Apertura garantiza streams utilizables

`SerialConnection` SHALL garantizar que, al reconectar, el puerto quede con
streams `readable` y `writable` utilizables antes de reportar la conexión
como establecida. Si el puerto reporta "ya abierto" (`InvalidStateError`)
pero sin streams utilizables (estado "abierto zombie" tras una
re-enumeración USB o un cierre incompleto), SHALL cerrarlo y reabrirlo para
obtener streams frescos. Si tras abrir no hay `readable`+`writable`,
`autoConnect()` SHALL devolver `false` y NO marcar `isConnected=true`.

#### Scenario: Reclamo cuando el puerto seguía abierto y usable

- **WHEN** `autoConnect()` intenta abrir un puerto que ya estaba abierto y
  con streams usables
- **THEN** la conexión se considera establecida sin reabrir

#### Scenario: Puerto "abierto zombie" tras re-enumeración

- **WHEN** el puerto reporta `InvalidStateError` al abrir pero
  `readable`/`writable` están en null
- **THEN** se cierra y reabre para obtener streams frescos, y solo se
  reporta conectado si quedan utilizables

#### Scenario: Escritura/lectura sin stream

- **WHEN** `write()` o `read()` se invocan y el stream correspondiente es
  null
- **THEN** no lanzan (no crashean con "reading 'getWriter'"), devuelven
  fallo y bajan `isConnected` para reflejar el estado real
