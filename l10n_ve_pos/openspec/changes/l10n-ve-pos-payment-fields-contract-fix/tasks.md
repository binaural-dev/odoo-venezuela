## 1. Fix

- [x] 1.1 `models/pos_payment.py::_load_pos_data_fields`: no construir el
      whitelist si `super()` ya devuelve una lista vacía; solo extender si
      ya viene no-vacía.
- [x] 1.2 Actualizar `test_pos_payment_load_pos_data_fields_includes_foreign_amount_and_rate`
      al idiom `not fields or "campo" in fields` (igual que
      `test_dynamic_models_expose_write_date`).

## 2. Verificación

- [ ] 2.1 Correr `test_pos_serialization.py` completo (no roto por el
      cambio de idiom del test 1.2, ni por el resto de tests de
      `pos.order`/`pos.order.line` que no se tocaron).
- [ ] 2.2 Reinstalar/actualizar `binaural_subsidiary_pos` en `2doce` y
      confirmar que el error *"The field 'sh_analytic_account' does not
      exist in model 'pos.payment'"* ya no ocurre al pulsar un método de
      pago.
