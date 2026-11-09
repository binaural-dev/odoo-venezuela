## 1. Implementación

- [x] 1.1 `_prepare_tax_lines` y `_apply_price_included_per_line` en `models/account_tax.py`.
- [x] 1.2 `_fix_base_amount_from_real_lines` (bases del widget desde las líneas reales).
- [x] 1.3 `_fix_foreign_summary_from_lines` (alterno del widget desde los apuntes).
- [x] 1.4 `_get_tax_group_product_lines` reemplaza el filtro duplicado de grupos de impuesto.

- [x] 1.5 `_round_tax_details_base_lines`: con Global, la diferencia de redondeo se reparte por grupo de impuesto.
- [x] 1.6 `_fix_base_amount_from_real_lines` también con Por línea.
- [x] 1.7 Bump de versión `19.0.1.0.42` -> `19.0.1.0.43`.

## 2. Tests

- [x] 2.1 `tests/test_global_price_included_exempt.py`: USD, VEF, EUR, mezcla, control sin exento,
  exento incluido en el precio (0 %), base VEF del IVA, subtotales encadenados, el centavo en su grupo
  (USD, EUR y VEF), grupo exento con dos líneas y widget con Por línea.
- [x] 2.2 Suite completa de `l10n_ve_accountant` y `l10n_ve_deductible` sin regresiones.

## 3. Verificación manual

- [ ] 3.1 Factura en USD con un producto exento y tres con IVA incluido (24,42×4 exento; 20,00×2,
  9,06×4 y 27,29×2 con IVA 16 % incluido) con método Global: el total debe ser 228,50 y el widget
  y el alterno deben coincidir con el asiento.
- [ ] 3.2 Reproducir el caso reportado (factura con precios de 4 decimales, tres líneas con IVA y una exenta
  de mayor base, redondeo global): el Exento no debe llevar el centavo del IVA.
- [ ] 3.3 Venta de POS con precios de más de 2 decimales: comparar el total del POS con el de su factura.
