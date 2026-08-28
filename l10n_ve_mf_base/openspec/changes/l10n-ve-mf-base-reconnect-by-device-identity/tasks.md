## 1. Implementación

- [x] 1.1 `autoConnect()` selecciona el puerto SOLO por identidad USB
      guardada (VID/PID, clave `fiscal_printer_device`). Sin identidad
      guardada NO adopta ningún puerto (ni el único) — adoptar a ciegas
      podría tomar/sondear/cerrar la balanza; el usuario fija la identidad
      conectando una vez desde el botón.
- [x] 1.2 La identidad se persiste SOLO tras verificar con `getStatus()`
      que el puerto responde como máquina fiscal (en
      `TfhkaDriver._verifyAndPersist`), no en `requestPort()`/`autoConnect()`
      — así nunca se guarda la balanza (u otro serial adoptado) como MF.
- [x] 1.3 `_openPort()` robusto: si el puerto reporta "ya abierto"
      (`InvalidStateError`) pero sin streams usables (readable/writable en
      null, típico tras re-enumeración USB), lo cierra y reabre para obtener
      streams frescos
- [x] 1.4 Helpers `_saveDeviceInfo()` / `_loadDeviceInfo()`
- [x] 1.5 `autoConnect()` verifica `readable`+`writable` antes de dar
      `isConnected=true`; `write()`/`read()` no crashean con streams null (y
      bajan `isConnected`); `disconnect()` suelta estado en `finally` aunque
      `close()` falle sobre un puerto difunto
      (fix del crash `Cannot read properties of null (reading 'getWriter')`)

## 2. Endurecimiento (code review TA 78328)

- [x] 2.1 Mutex de reconexión en `TfhkaDriver.connect()` (promesa
      `_connecting` en curso): serializa a los múltiples llamadores (montaje,
      listener USB, click, reclaim) para que dos `autoConnect()` no se
      interleaven en `_openPort`. `disconnect()` espera esa promesa antes de
      cerrar (evita disconnect-durante-connect). `_doConnect` usa
      `connection.disconnect()` de bajo nivel para no auto-esperarse.
- [x] 2.2 En verificación fallida (`getStatus()` null), `_doConnect` suelta
      el puerto (`connection.disconnect()`) en vez de retenerlo, y cae al
      prompt si estaba pedido.
- [x] 2.3 `write()` aborta (return false) si expira la espera del `writeLock`
      en vez de forzarlo (no pisa una escritura en vuelo).

## 3. Verificación

- [x] 3.1 Sintaxis (`node --check`)
- [ ] 3.2 Navegador con la MF autorizada: primer arranque sin identidad →
      un click en el botón (requestPort) fija la identidad; luego la
      reconexión silenciosa es automática por VID/PID
- [ ] 3.3 Navegador con balanza + MF autorizadas: `autoConnect()` reabre la
      MF y no toca la balanza; una re-enumeración durante el hand-off no
      corrompe la conexión (mutex)
- [ ] 3.4 MF que abre pero no responde a `getStatus()` → se suelta el puerto
      (no queda retenido) y el hand-off puede cederlo
