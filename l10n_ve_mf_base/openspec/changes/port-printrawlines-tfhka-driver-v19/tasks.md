## 1. Implementación

- [x] 1.1 Confirmar que `sendCommand`, `abortTransaction`, `getStatus`,
      `_isWaitingState` y `_formatSts` existen en el `TfhkaDriver.js` de la
      rama `19.0` con la misma firma y semántica que en `origin/17.0`
      (commit `29b517b4e`).
- [x] 1.2 Portar `printRawLines(lines)` desde `origin/17.0:l10n_ve_mf_base/
      static/src/drivers/TfhkaDriver.js` (commit `29b517b4e`) al
      `TfhkaDriver.js` de 19.0, insertado entre `abortTransaction()` y
      `getStatus()` (mismo orden relativo que en 17.0), sin `withConnection()`
      ni ningún patrón de conexión por-llamada de 17.0.
- [x] 1.3 `grep -rn "printRawLines" --include="*.js" .` sobre todo
      `odoo-venezuela` para confirmar que no hay otros consumidores internos
      que sugieran exponer el método en otra capa (`l10n_ve_pos_mf` incluido).
- [x] 1.4 Bump de versión en `l10n_ve_mf_base/__manifest__.py`
      (`19.0.1.1.1` → `19.0.1.1.2`), siguiendo el esquema de bumps de patch ya
      usado por el módulo.

## 2. Verificación

- [x] 2.1 `node --check` sobre `TfhkaDriver.js`.
- [ ] 2.2 Validación con máquina fiscal TFHKA real conectada por Web Serial
      (voucher con líneas de formato libre) — requiere navegador + hardware,
      fuera del alcance de esta tarea.
- [ ] 2.3 Validación end-to-end desde `binaural_pos_sitef_integration`
      (venta con tarjeta/pago móvil aprobada por Sitef → voucher impreso) —
      corresponde a la fase 9 de `migrate-binaural-pos-sitef-integration-v19`.
