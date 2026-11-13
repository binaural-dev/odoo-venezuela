# Fix: el Kiosko trabaja con la tasa del día de apertura de su sesión (ti 16351)

## Why

Ticket 16351 (referencia #16389): una sesión del PdV trabaja siempre con la tasa del día de su apertura
(`l10n_ve_pos`, `pos.session.foreign_rate_date`). La caja del Kiosko toma esa tasa por `pos.config`, pero
las monedas las lee por `res.currency._load_pos_self_data_read` (un `read` directo del core), que no pasa
por `_load_pos_data_read` de `l10n_ve_pos`: recibía el `rate` del momento de la carga. Después de
medianoche, o de 20:00 a 24:00 con un usuario sin zona horaria, la lista de precios en divisa se convertía
con una tasa y el total en divisa con otra.

## What Changes

- `res.currency._load_pos_self_data_read`: aplica la tasa del día de la sesión
  (`res.currency._apply_pos_session_rates` de `l10n_ve_pos`), la misma que recibe el PdV.
- Sin tasa del día el Kiosko no abre: `action_open_wizard` abre la sesión con `set_opening_control`, que
  en `l10n_ve_pos` lanza el error (la sesión creada se revierte con la transacción).
- Versión 19.0.1.7.1 → 19.0.1.8.0.

## Non-goals

- Un Kiosko abierto varios días factura con la tasa del día de su apertura sin aviso (no usa el `PosStore`
  del PdV). Se recomienda cerrarlo a diario.

## Impact

- Depende del cambio de `l10n_ve_pos` del mismo PR (`_apply_pos_session_rates`, `foreign_rate_date`).
- Despliegue: `-u l10n_ve_pos,l10n_ve_pos_self_order`.
