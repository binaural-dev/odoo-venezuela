## Why

El hand-off del puerto COM (ceder la máquina fiscal a un proceso externo y
reclamarla después) vivía duplicado en `binaural_megasoft`
(`PosState.js`), un módulo que a propósito NO depende de la máquina fiscal.
El dueño natural del puerto de la MF es `l10n_ve_pos_mf`.

Además, en producción (cliente 2doce: PCs de 4GB con balanza + máquina
fiscal + pinpad de Megasoft, todos sobre Web Serial en la misma pestaña)
la MF se "soltaba" tras cada transacción de Megasoft y había que
re-vincularla a mano. Causas detectadas:

- La reconexión silenciosa reabría `getPorts()[0]` (el primer puerto
  autorizado de la pestaña, que con varios dispositivos podía ser la
  balanza, no la MF) → `getStatus()` no respondía → reclamo fallido → el
  cajero tenía que re-vincular con el diálogo. (Fix hermano en
  `l10n_ve_mf_base`, ver cambio `l10n-ve-mf-base-reconnect-by-device-identity`.)
- No había ninguna recuperación cuando el dispositivo re-enumeraba en el
  bus USB a media sesión (glitch de energía del hub, típico en PCs de gama
  baja): la MF quedaba desconectada hasta un click manual.

## What Changes

- `overrides/PosStore.js`:
  - Nuevo método público `withFiscalPrinterReleased(criticalSection)`:
    cede el puerto (`disconnect()` si la MF está conectada), ejecuta la
    sección crítica externa, y en el `finally` reclama el puerto con
    reintentos silenciosos; si falla, avisa. Propaga intactos el resultado
    y las excepciones de `criticalSection`.
  - Se mueven aquí desde `binaural_megasoft` las piezas del mecanismo:
    constantes `MF_PORT_HANDOFF_GRACE_MS` (1000ms),
    `MF_PORT_RECLAIM_MAX_ATTEMPTS` (3), `MF_PORT_RECLAIM_RETRY_DELAY_MS`
    (750ms), y los métodos `_reclaimFiscalPrinterPort()`,
    `_notifyFiscalPrinterReclaimFailed()`, `_sleep()`.
- `components/FiscalPrinterButton/FiscalPrinterButton.js`:
  - Listeners `navigator.serial` `connect`/`disconnect` para recuperación
    mid-sesión ante re-enumeración USB, con limpieza en `onWillUnmount`.
  - `connect`: reconexión silenciosa (`fp.connect()` → `autoConnect()`,
    que ya filtra por identidad); solo tiene éxito si es la MF.
  - `disconnect`: si el puerto que desaparece es el nuestro, refleja estado
    "desconectado" (el listener de `connect` lo recupera si vuelve).

## Capabilities

### Modified Capabilities

- `pos-fiscal-printer-webserial`: se agrega (1) un hand-off de puerto
  reutilizable por cualquier integración externa que necesite el mismo COM
  (hoy Megasoft), y (2) recuperación automática de la conexión ante
  re-enumeración USB a media sesión.

## Impact

- Módulo: `l10n_ve_pos_mf` (`overrides/PosStore.js`,
  `components/FiscalPrinterButton/FiscalPrinterButton.js`).
- Depende del cambio hermano `l10n-ve-mf-base-reconnect-by-device-identity`
  (reconexión por VID/PID) para que el reclamo silencioso reabra el puerto
  correcto cuando hay varios seriales autorizados.
- `binaural_megasoft` ahora consume `withFiscalPrinterReleased` vía
  feature-detection (`typeof this.withFiscalPrinterReleased === "function"`),
  sin dependencia dura: si `l10n_ve_pos_mf` no está instalado, llama al
  VPOS directo como antes.
- El texto del aviso de reclamo fallido pasa a ser genérico ("operación
  externa") en vez de específico de Megasoft, y va dentro de `_t()`.
- No verificable end-to-end sin MF + Megasoft real conectados; sintaxis
  validada con `node --check`. Verificación en navegador pendiente.
