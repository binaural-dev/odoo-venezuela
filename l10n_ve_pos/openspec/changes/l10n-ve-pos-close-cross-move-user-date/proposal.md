# Fix: el asiento de cruce del cierre se fecha con el día del usuario (l10n_ve_pos)

## Why

Al cerrar la caja después de las 8 pm (hora de Caracas, UTC-4) el cierre se
detenía con `No hay una tasa asignada para <moneda> al <día siguiente>`, aunque
la zona horaria del usuario fuera `America/Caracas`.

### Causa raíz

`_validate_cross_move` pasaba `session.stop_at or fields.Datetime.now()` y
`payment.create_date` (Datetime en UTC) como `date` de `_create_cross_move_for`.
Asignados al campo `Date` del asiento se truncan a la fecha UTC, que a las 8 pm de
Caracas ya es la del día siguiente. `l10n_ve_rate` solo acepta la tasa de la fecha
exacta del asiento, así que no la encontraba.

## What changes

- `models/pos_session.py::_validate_cross_move`: la fecha del asiento es
  `fields.Date.context_today(session, <datetime>)`, el día del usuario.
- Conversiones con un Datetime UTC (`stop_at`, `payment_date`, `date_order`):
  `res.currency._convert` toma la última tasa con fecha menor o igual, y con la tasa
  del día siguiente ya publicada convertía con esa y no con la del día de los
  asientos. Se normaliza en `pos.session._amount_converter` (lo usan el core,
  `_update_amounts`, `l10n_ve_pos_igtf` y `binaural_pos_multicurrency`) y en
  `_prepare_statement_line_amount_values` (el core convierte con `stop_at`).
- Pruebas `tests/test_pos_session_close_tz_boundary.py` (reloj a las 20:30 de
  Caracas, tasa del día del usuario y la de mañana ya cargada).
