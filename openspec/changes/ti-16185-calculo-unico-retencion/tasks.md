## 1. l10n_ve_payment_extension — cálculo único

- [x] 1.1 `compute_iva_retention_amount` y su uso en `compute_retention_lines_data` y `_apply_iva_tax_group_values`
- [x] 1.2 `_retention_amount_tolerance` como única regla de redondeo; `_retention_difference_within_currency_precision` la usa
- [x] 1.3 Pruebas: helper, líneas cargadas, seguimiento de un cambio en el helper, y tolerancia contra la regla de redondeo a seis tasas

## 2. Verificación

- [ ] 2.1 Correr `retention_amount_tolerance` y `retention_iva_amount_single_calculation` tras el upgrade del módulo
