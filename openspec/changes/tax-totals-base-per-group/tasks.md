## 1. l10n_ve_accountant — base_amount por grupo en tax_totals

- [x] 1.1 `_fix_base_amount_for_multi_currency`: reemplazar el reparto proporcional entre `tax_groups` por la suma real de `balance` de las líneas de producto de cada grupo (match por `involved_tax_ids`, con fallback a `children_tax_ids` para taxes tipo 'group')
- [x] 1.2 Mantener el reparto proporcional como respaldo defensivo si no se identifican líneas propias de un grupo
- [x] 1.3 Bump de manifest `l10n_ve_accountant` 19.0.1.0.22 → 19.0.1.0.23
- [x] 1.4 Tests (`tests/test_multi_currency_rounding.py`): dos grupos distintos en factura de proveedor y de cliente, tres grupos distintos, y un tax tipo 'group' con hijos que comparten base + un grupo independiente

## 2. Verificación

- [x] 2.1 Reproducir el caso real con tasa BCV con muchos decimales y precisión de precio a 6 decimales: sin el fix, el test falla con ~2,64 Bs de diferencia entre el widget y la línea real
- [x] 2.2 Con el fix, el `base_amount` de cada grupo coincide al céntimo con la suma real de sus propias líneas
- [x] 2.3 Regresión: las pruebas existentes de `l10n_ve_accountant` (real_portion, rounding, tax_foreign) siguen en verde
- [x] 2.4 Regresión: las pruebas de `l10n_ve_igtf` (que depende de `l10n_ve_accountant`) siguen en verde
