## 1. Implementación

- [x] 1.1 `pos.session._create_cross_move`: un Datetime (`stop_at`, `create_date` del pago) se pasa al día del usuario
      con `fields.Date.context_today` antes de crear el asiento; una fecha pasa sin cambios
- [x] 1.2 Versión del manifest 19.0.1.28.2
- [x] 1.3 Archivar el change y volcarlo en `openspec/specs/l10n_ve_pos/spec.md`

## 2. Tests

- [x] 2.1 `tests/test_pos_session_cross_account_move.py`: cierre a las 8:30 pm de Caracas con tasa solo del día local,
      método en efectivo sin "Identificar cliente" (`stop_at`) y con "Identificar cliente" (`create_date` del pago):
      el cruce queda del día local. Sin el fix los dos fallan con "No hay una tasa asignada para VEF al 2026-03-11"
      (`odoo --test-tags /l10n_ve_pos:TestPosSessionCrossAccountMove`)
- [x] 2.2 Suites de `l10n_ve_pos`, `l10n_ve_pos_igtf` y `binaural_pos_close` en `nova_db` (copia de Nova), y además
      `binaural_pos_multicurrency` en una base nueva: los mismos fallos con y sin el fix (previos de esas bases);
      con el fix pasan los 2 tests nuevos
- [x] 2.3 Cierre de punta a punta en `nova_db` (rollback): apertura de "C2 - AV. VICTORIA", venta pagada en
      "EFECTIVO USD C2", conteo de cierre, "Control de cierre" con `stop_at` a las 9:35 pm de Caracas y el botón
      "Cerrar sesión" del backend (`action_pos_session_closing_control`). Sin el fix: "No hay una tasa asignada para
      USD al <mañana>"; con el fix la sesión cierra y el cruce queda en borrador con la fecha del día local

## 3. Decisiones

- [x] 3.1 2026-11-02: corregir en `_create_cross_move`, por donde pasan todos los cruces (`l10n_ve_pos`,
      `binaural_pos_close`, `binaural_pos_multicurrency`), en vez de en cada llamador
- [x] 3.2 2026-11-02: se conserva la fuente de la fecha de cada granularidad (`stop_at` y `create_date` del pago);
      solo cambia la conversión a día
