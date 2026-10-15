## 1. l10n_ve_accountant — payment_state stuck tras romper conciliación

- [x] 1.1 `AccountPartialReconcile.unlink()`: fuerza `payment_state` a "pendiente de recalcular" (perezoso, `env.add_to_compute`) en las facturas/pagos tocados por la conciliación borrada
- [x] 1.2 Recompute perezoso, no eager: un `_compute_payment_state()` inmediato dentro de `unlink()` captura estados intermedios en flujos que borran y recrean una conciliación en la misma operación (cruce de anticipo)

## 2. l10n_ve_exchange_difference — no sobreescribir un 'reversed' genuino

- [x] 2.1 `_compute_payment_state`: si `remaining_types` queda vacío (la nota propia es la ÚNICA contraparte restante), no forzar `'paid'` -- ese es exactamente el caso base de `'reversed'` del núcleo

## 3. Manifest y tests

- [x] 3.1 Bump `l10n_ve_accountant` 19.0.1.0.23 → 19.0.1.0.24
- [x] 3.2 Bump `l10n_ve_exchange_difference` 19.0.0.0.3 → 19.0.0.0.4
- [x] 3.3 Test de regresión: 3 pagos reales vía wizard, desconciliados uno por uno, `payment_state` vuelve a `'not_paid'` (`test_55_unreconcile_normal_payment_updates_payment_state`)
- [x] 3.4 Test de regresión: factura cerrada por cruce de anticipo + NC de diferencial cierra `'paid'`, no `'reversed'` (`test_invoice_closed_by_advance_cross_and_note_does_not_end_up_reversed`)

## 4. Verificación

- [x] 4.1 Ambos tests corridos en aislado (sin el resto de la suite), sobre esta rama, base limpia desde `maintenance-19.0` -- EXIT 0
- [x] 4.2 Confirmado contra un caso real de producción (factura/pago con `payment_account_id` propio en el diario del banco) que sin el fix `payment_state` se queda en `'paid'` con `amount_residual` de vuelta al total de la factura
