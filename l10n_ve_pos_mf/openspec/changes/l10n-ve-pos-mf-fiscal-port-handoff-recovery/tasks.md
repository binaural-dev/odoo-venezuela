## 1. Hand-off del puerto (mover desde binaural_megasoft)

- [x] 1.1 Constantes `MF_PORT_HANDOFF_GRACE_MS`, `MF_PORT_RECLAIM_MAX_ATTEMPTS`,
      `MF_PORT_RECLAIM_RETRY_DELAY_MS` a nivel de módulo en `PosStore.js`
- [x] 1.2 `_sleep()`, `_reclaimFiscalPrinterPort()`,
      `_notifyFiscalPrinterReclaimFailed()` movidos aquí (aviso genérico + `_t()`)
- [x] 1.3 Nuevo `withFiscalPrinterReleased(criticalSection)` que envuelve
      disconnect → sección → reclaim en `finally`, propagando resultado/errores

## 2. Recuperación mid-sesión (FiscalPrinterButton)

- [x] 2.1 Import de `onWillUnmount`
- [x] 2.2 Registrar listeners `navigator.serial` `connect`/`disconnect` en
      `onMounted`, quitarlos en `onWillUnmount`
- [x] 2.3 `_onSerialConnect`: reconexión silenciosa si la MF no está conectada
- [x] 2.4 `_onSerialDisconnect`: marcar desconectado solo si el puerto que
      desaparece es el nuestro
- [x] 2.5 `_onSerialConnect`: `disconnect()` antes de reconectar (equivale al
      "apagar/prender" manual, único camino que reconectaba limpio) +
      guarda de reentrada y de estado "connecting" (evita dos connect()
      concurrentes y el puerto medio-abierto tras re-enumeración)

## 3. Verificación

- [x] 3.1 Sintaxis (`node --check`)
- [x] 3.2 Sin `l10n_ve_pos_mf`/hook: `binaural_megasoft` cae al camino directo
      (feature-detection) — revisado en el consumidor
- [ ] 3.3 Navegador: con MF + Megasoft reales, confirmar que tras la
      transacción la MF se reclama sola (sin re-vincular) y el overlay cubre
      todo el ciclo
- [ ] 3.4 Navegador: desconectar/reconectar físicamente la MF a media sesión
      y confirmar que el botón vuelve a "connected" sin click manual
