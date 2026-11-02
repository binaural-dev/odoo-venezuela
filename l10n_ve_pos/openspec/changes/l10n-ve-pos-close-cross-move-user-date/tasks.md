# Tasks

## 1. Diagnóstico

- [x] 1.1 Reproducir el error con `freeze_time` a las 20:30 de Caracas y tasa solo
      para el día del usuario (`There is no rate assigned for VEF on <día UTC>`)
- [x] 1.2 Ubicar la causa: Datetime UTC asignado al `date` del asiento de cruce

## 2. Implementación

- [x] 2.1 `_validate_cross_move`: `fields.Date.context_today(session, ...)` en las
      dos llamadas a `_create_cross_move_for`
- [x] 2.2 `_amount_converter` y `_prepare_statement_line_amount_values`: Datetime UTC → día del usuario
- [x] 2.3 Subir la versión del módulo a 19.0.1.28.2

## 3. Validación

- [x] 3.1 `tests/test_pos_session_close_tz_boundary.py` (tag `l10n_ve_pos_tz_boundary`):
      3 errores sin el arreglo, pasan con él
- [x] 3.3 Conversiones (`TestPosSessionConversionDate`, tag `l10n_ve_pos_tz_conversion`): 3 fallos con la tasa de mañana (2,0 contra 2,5), pasan con el arreglo
- [x] 3.2 Suite completa de `l10n_ve_pos` en una BD nueva y sin demo: 140 tests, 0 fallos; `l10n_ve_pos_igtf`: 7 tests, 0 fallos
