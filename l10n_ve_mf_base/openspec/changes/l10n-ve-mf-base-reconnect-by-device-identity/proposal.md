## Why

`SerialConnection.autoConnect()` reabría el puerto con
`navigator.serial.getPorts()[0]` — el PRIMER puerto autorizado de la
pestaña. En cajas con un solo dispositivo Web Serial funciona por
casualidad, pero el cliente 2doce tiene balanza + pinpad de Megasoft +
máquina fiscal, todos autorizados en la misma pestaña. Ahí `[0]` podía ser
la balanza: `autoConnect()` abría el puerto equivocado, `getStatus()` no
respondía, la reconexión se daba por fallida y el cajero tenía que
re-vincular la máquina fiscal a mano — de forma reproducible tras cada
hand-off del puerto en las transacciones de Megasoft.

Esto no aparecía en la VM de pruebas del desarrollador porque ahí solo
estaba autorizada la máquina fiscal (un único puerto → `[0]` siempre
correcto).

## What Changes

- `static/src/core/SerialConnection.js`:
  - `requestPort()`: además de guardar la config, persiste la identidad USB
    (`getInfo()` → `usbVendorId`/`usbProductId`) en `localStorage`
    (`fiscal_printer_device`).
  - `autoConnect()`: selecciona el puerto por identidad guardada
    (`getPorts().find(...)` por VID/PID) en vez de `[0]`. Si no hay
    identidad guardada (puertos autorizados antes de esta versión) y hay un
    único puerto, lo usa (compatibilidad); con varios puertos y sin
    identidad, no adivina: devuelve `false` y pide un reconecte manual (que
    fija la identidad y a partir de ahí es automático).
  - Nuevo helper `_openPort()` que tolera `InvalidStateError` (puerto ya
    abierto) al reclamar tras un hand-off.
  - Helpers `_saveDeviceInfo()` / `_loadDeviceInfo()`.

## Capabilities

### Modified Capabilities

- `serial-connection`: la reconexión automática pasa de posicional
  (`getPorts()[0]`) a por identidad USB (VID/PID), y la apertura tolera que
  el puerto ya esté abierto.

## Impact

- Módulo: `l10n_ve_mf_base` (`static/src/core/SerialConnection.js`).
- Habilita el fix real del síntoma "la máquina fiscal se suelta tras cada
  transacción de Megasoft" cuando conviven varios seriales; es la base del
  cambio hermano `l10n-ve-pos-mf-fiscal-port-handoff-recovery`.
- Migración: en instalaciones existentes, la primera reconexión silenciosa
  tras el deploy puede fallar si hay >1 puerto autorizado y aún no hay
  identidad guardada; un único click en el botón de la máquina fiscal fija
  la identidad y lo deja automático de ahí en adelante. Es más seguro que
  el comportamiento anterior (abrir a ciegas el puerto equivocado).
- Sintaxis validada con `node --check`. Verificación en navegador con
  balanza + MF simultáneas pendiente.
