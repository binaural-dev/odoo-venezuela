## 1. Implementación

- [x] 1.1 `requestPort()` persiste identidad USB (`_saveDeviceInfo()`,
      clave `fiscal_printer_device`)
- [x] 1.2 `autoConnect()` selecciona por VID/PID; fallback a puerto único
      sin identidad; sin adivinar con varios puertos
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

## 2. Verificación

- [x] 2.1 Sintaxis (`node --check`)
- [ ] 2.2 Navegador con un solo puerto autorizado: reconexión silenciosa
      sigue funcionando (fallback e identidad)
- [ ] 2.3 Navegador con balanza + MF autorizadas: `autoConnect()` reabre la
      MF y no la balanza
- [ ] 2.4 Migración: puerto autorizado antes del deploy (sin identidad) +
      un segundo puerto → primer reconecte manual fija identidad, luego
      automático
