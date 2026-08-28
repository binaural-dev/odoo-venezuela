# Tasks: cruce de ventas siempre a la Cuenta Transitoria

## 1. Parámetro `real_to_suspense` en la cadena de cruce
- [x] 1.1 `_get_cross_real_account(..., real_to_suspense=False)`: devolver
  `cross_journal.suspense_account_id` cuando `use_suspense or real_to_suspense`.
- [x] 1.2 `_line_vals_move_cross_incoming`/`_outgoing`: aceptar `real_to_suspense` y
  reenviarlo a `_get_cross_real_account`.
- [x] 1.3 `_create_cross_move_for`: aceptar `real_to_suspense` y reenviarlo al
  builder. Verificar que NO altera la rama entrante/saliente ni la inversión (esa
  sigue gobernada solo por `use_suspense`).

## 2. Conectar solo la ruta de ventas, siempre activa
- [x] 2.1 `_validate_cross_move`: en las dos granularidades (split y combine) pasar
  `real_to_suspense=True` (incondicional).
- [x] 2.2 Confirmar que `_post_foreign_statement_difference` (binaural_pos_close) NO
  pasa el parámetro → diferencias sin cambios.
- [x] 2.3 Confirmar que cash in/out (`use_suspense=True`) no se ve afectado.

## 3. Sin configuración
- [x] 3.1 No agregar campo `cross_sales_to_suspense` (ni a modelo, vista, `.po`,
  `_load_pos_data_fields`). Comportamiento único.

## 4. Manifest y verificación
- [x] 4.1 Versión 1.10 → 1.11.
- [ ] 4.2 `-u l10n_ve_pos` y validar en navegador: una venta en efectivo foráneo
  cruza `journal_id.default_account_id` (origen, sin cambio) contra
  `cross_journal.suspense_account_id` (destino), misma cuenta que cash in/out.
- [ ] 4.3 Confirmar que las diferencias de apertura/cierre no cambiaron de cuenta
  destino.
- [ ] 4.4 Tests (`tests/test_pos_session_cross_account_move.py`): ajustar/añadir el
  caso de ventas para que el destino sea la suspense del `cross_journal`; caso
  diferencia sin afectar. (pendiente de correr por el usuario)
