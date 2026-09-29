## ADDED Requirements

### Requirement: Hand-off reutilizable del puerto de la máquina fiscal

`l10n_ve_pos_mf` SHALL exponer en `PosStore` un método
`withFiscalPrinterReleased(criticalSection)` que ceda el puerto de la
máquina fiscal a una sección crítica externa y lo reclame después. Si la
máquina fiscal está conectada, SHALL desconectarla antes de ejecutar
`criticalSection` y reclamarla (reconexión silenciosa con reintentos)
en un bloque `finally`. Si la máquina fiscal no está conectada, SHALL
ejecutar `criticalSection` sin manipular ningún puerto. El valor devuelto
y las excepciones de `criticalSection` SHALL propagarse intactos.

#### Scenario: Máquina fiscal conectada durante la sección crítica

- **WHEN** se llama `withFiscalPrinterReleased(fn)` con la MF conectada
- **THEN** se desconecta la MF, se ejecuta `fn`, y luego se intenta
  reclamar el puerto antes de devolver el resultado de `fn`

#### Scenario: Máquina fiscal no conectada

- **WHEN** se llama `withFiscalPrinterReleased(fn)` sin MF conectada
- **THEN** se ejecuta `fn` sin desconectar ni reconectar ningún puerto, y
  se devuelve su resultado

#### Scenario: Reclamo del puerto agotado

- **WHEN** tras ejecutar la sección crítica todos los reintentos de
  reconexión de la MF fallan
- **THEN** se muestra una notificación no-modal (`sticky`) pidiendo
  verificar la conexión de la máquina fiscal, y el método retorna igual

### Requirement: Recuperación automática ante re-enumeración USB

El botón de la máquina fiscal SHALL escuchar los eventos
`navigator.serial` `connect` y `disconnect` mientras esté montado, y
SHALL retirar esos listeners al desmontarse. Ante un `connect`, si la MF
no está conectada, SHALL intentar una reconexión silenciosa (que reabre
solo el dispositivo cuya identidad coincide con la MF). Ante un
`disconnect` del puerto de la MF, SHALL reflejar el estado como
desconectado.

#### Scenario: El dispositivo fiscal reaparece en el bus

- **WHEN** llega un evento `connect` de `navigator.serial` y la MF figura
  como desconectada
- **THEN** se intenta reconectar en silencio y, si la identidad coincide,
  el estado del botón pasa a "conectado" sin intervención del cajero

#### Scenario: El dispositivo fiscal desaparece del bus

- **WHEN** llega un evento `disconnect` cuyo puerto es el de la MF
- **THEN** el estado del botón pasa a "desconectado"

#### Scenario: Evento de otro dispositivo serial

- **WHEN** llega un evento `connect`/`disconnect` de un dispositivo que no
  es la máquina fiscal (p.ej. la balanza)
- **THEN** la reconexión silenciosa no reabre la MF por error y el estado
  de la MF no cambia por un `disconnect` ajeno
