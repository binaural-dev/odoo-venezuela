## 1. l10n_ve_pos — cruce de venta en efectivo entre transitorias

- [x] 1.1 `_validate_cross_move`: calcular `use_suspense = payment_method.type == "cash"` por método y pasarlo tanto al filtro de elegibilidad (`_is_cross_move_eligible`) como a `_create_cross_move_for`, en las dos granularidades (split y combine)
- [x] 1.2 Revisar que el filtro inicial de `payments` evalúe la elegibilidad con el flag correcto por método (hoy filtra una sola vez sin flag)
- [x] 1.3 Actualizar los docstrings de `_validate_cross_move`, `_get_cross_transitory_account` y `_get_cross_real_account` para que `use_suspense` ya no se describa como "solo cash in/out"
- [x] 1.4 Bump de manifest `l10n_ve_pos` 1.17 → 1.18

## 2. Tests (`tests/test_pos_session_cross_account_move.py`)

- [x] 2.1 Venta en efectivo divisa: el asiento debita `journal_id.suspense_account_id` y acredita `cross_journal.suspense_account_id`, y NO toca `journal_id.default_account_id` ni la `payment_account_id` del `cross_journal`
- [x] 2.2 Neto negativo en efectivo: asiento espejo (debita la transitoria del `cross_journal`, acredita la del método)
- [x] 2.3 Regresión banco: el método `bank` sigue cruzando `outstanding_account_id` → cuenta real del `cross_journal`
- [x] 2.4 Regresión diferencias de cierre: ya cubierta fuera de este repo por `binaural_pos_close/tests/test_pos_close_migration.py`, que sigue afirmando `default_account_id` para `_post_foreign_statement_difference`
- [x] 2.5 Método en efectivo cuyo diario no tiene Cuenta transitoria → no se crea asiento y el cierre no falla
- [x] 2.6 Montos alternos, tasa, `ref`, diario y estado borrador del asiento sin cambios
- [x] 2.7 Destino sin Cuenta transitoria → se omite y NO revienta el cierre (hallazgo de code review)
- [x] 2.8 Las dos transitorias en la misma cuenta → el asiento se emite igual (decisión del ticket)

## 3. Verificación en `vzla19_lebrum` (instancia electricos-lebrum, puerto 8083)

- [ ] 3.1 Configurar Cuenta transitoria propia en el diario 371 `POS EFECTIVO DOLARES C1 C.A.` (hoy comparte `1.7.1.06` con el diario afectado 359, lo que haría el asiento nulo)
- [ ] 3.2 Sesión de prueba en CAJA 1: ventas en efectivo divisa + salida de efectivo por el total al cierre
- [ ] 3.3 Comprobar en el asiento de cruce de la venta: DEBE transitoria del diario del método, HABER transitoria del diario afectado
- [ ] 3.4 Comprobar que la cuenta POS del diario del método (`1.7.1.38` / `1.7.1.37` / `1.6.6.6.01`) cierra la sesión en cero contra la salida de efectivo
- [ ] 3.5 Comprobar que, tras la conciliación del diario del método contra la cuenta del diario principal, ambas transitorias quedan en cero
