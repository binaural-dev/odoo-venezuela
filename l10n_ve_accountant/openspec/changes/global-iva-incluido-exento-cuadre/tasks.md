## 1. Implementación

- [x] 1.1 `_prepare_tax_lines` y `_apply_price_included_per_line` en `models/account_tax.py`.
- [x] 1.2 `_fix_base_amount_from_real_lines` (bases del widget desde las líneas reales).
- [x] 1.3 `_fix_foreign_summary_from_lines` (alterno del widget desde los apuntes).
- [x] 1.4 `_get_tax_group_product_lines` reemplaza el filtro duplicado de grupos de impuesto.

## 2. Tests

- [x] 2.1 `tests/test_global_price_included_exempt.py`: USD, VEF, EUR, mezcla, control sin exento,
  exento incluido en el precio (0 %), base VEF del IVA y subtotales encadenados.
- [x] 2.2 Suite completa de `l10n_ve_accountant` y `l10n_ve_deductible` sin regresiones.

## 3. Verificación manual

- [ ] 3.1 Factura en USD con un producto exento y tres con IVA incluido (24,42×4 exento; 20,00×2,
  9,06×4 y 27,29×2 con IVA 16 % incluido) con método Global: el total debe ser 228,50 y el widget
  y el alterno deben coincidir con el asiento.
