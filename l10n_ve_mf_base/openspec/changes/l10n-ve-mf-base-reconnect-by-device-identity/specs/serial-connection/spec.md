## MODIFIED Requirements

### Requirement: Reconexión automática por identidad del dispositivo

`SerialConnection.autoConnect()` SHALL seleccionar el puerto a reabrir por
identidad USB (VID/PID) guardada, y no por posición en
`navigator.serial.getPorts()`. `requestPort()` SHALL persistir la
identidad (`getInfo()`) del puerto elegido para que la reconexión posterior
pueda identificarlo. Cuando no exista identidad guardada, `autoConnect()`
SHALL reconectar solo si hay exactamente un puerto autorizado; con varios
puertos y sin identidad SHALL abstenerse (devolver `false`) en vez de abrir
uno al azar.

#### Scenario: Varios seriales autorizados, reconexión a la máquina fiscal

- **GIVEN** la pestaña tiene autorizados el puerto de la máquina fiscal y
  el de la balanza, y la identidad de la MF está guardada
- **WHEN** se llama `autoConnect()`
- **THEN** se reabre el puerto cuya identidad USB coincide con la máquina
  fiscal, sin importar su posición en `getPorts()`

#### Scenario: Compatibilidad con un único puerto sin identidad guardada

- **GIVEN** hay un solo puerto autorizado y no hay identidad guardada
  (autorizado antes de esta versión)
- **WHEN** se llama `autoConnect()`
- **THEN** se reabre ese único puerto y se guarda su identidad

#### Scenario: Varios puertos sin identidad guardada

- **GIVEN** hay más de un puerto autorizado y no hay identidad guardada
- **WHEN** se llama `autoConnect()`
- **THEN** no se abre ningún puerto (se devuelve `false`) y se registra un
  aviso pidiendo reconectar la máquina fiscal una vez desde el botón

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
