## 1. Backend

- [x] 1.1 `pos_payment.py::_create_payment_moves`: escribir `foreign_rate`,
  `foreign_inverse_rate`, `manually_set_rate=True` en `payment_move` después
  de `payment_move._post()`, con los mismos valores que usa `l10n_ve_pos`
  (`payment.foreign_rate`)

## 2. Verificación funcional

- [ ] 2.1 Probar en POS real: pago con IGTF, revisar en el asiento contable
  generado que `foreign_rate`/`foreign_inverse_rate`/`manually_set_rate`
  quedan poblados con la tasa del pago y no se sobreescriben con la tasa del
  día tras guardar/recargar el asiento
