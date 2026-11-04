## 1. l10n_ve_accountant — campo nuevo y eliminación del viejo

- [x] 1.1 Elimina `price_unit_ves`/`ves_currency_id` (`account_move_line.py`)
- [x] 1.2 Agrega `company_currency_line_totals` (Json, store=True) en `account.move`
- [x] 1.3 `_prorate_company_currency_amount`: reparto de mayor-residuo sobre el monto total fijo, no sobre el remanente que se achica en cada iteración (bug encontrado por code review)
- [x] 1.4 Match de impuestos por jerarquía aplanada (`flatten_taxes_hierarchy`), para que los de tipo `group` no se descarten en silencio (bug encontrado por code review)
- [x] 1.5 Signo de cada línea desde `price_subtotal`, no de un `abs(balance)` ciego (bug encontrado por code review)
- [x] 1.6 Excluye líneas `cogs` del desglose (no son líneas de factura)
- [x] 1.7 Migración `19.0.1.0.24`: dropea columnas huérfanas; bump de manifest a `19.0.1.0.25`

## 2. l10n_ve_invoice — integración

- [x] 2.1 Override de `_compute_company_currency_line_totals` para el caso `discount_fixed`
- [x] 2.2 Reporte `report_invoice_free_form`: columna de precio unitario usa el campo nuevo
- [x] 2.3 Bump de manifest a `19.0.1.0.23`

## 3. Tests

- [x] 3.1 `test_real_portion.py`: helper `_assert_balances` valida el campo en las ~40 pruebas existentes del archivo
- [x] 3.2 `test_coverage_gaps.py`: helper `_create_invoice` valida el campo en las ~60 pruebas existentes
- [x] 3.3 `test_account_move_line_fixed_discount.py`: helper `_create_invoice` valida el campo en las ~20 pruebas existentes; tests dedicados de `discount_fixed` en USD y EUR
- [x] 3.4 Casos dedicados: factura en EUR, impuesto `price_include`, descuento porcentual, 10 líneas con 3 tasas mezcladas y precisión no entera, reparto exacto con 3+ líneas de una misma tasa, impuesto tipo `group`, línea negativa (documentado como bloqueado por regla de negocio existente en `l10n_ve_invoice`)

## 4. Verificación

- [x] 4.1 116 pruebas (`l10n_ve_accountant` + `l10n_ve_invoice`, tags TestRealPortion/TestCoverageGaps/TestAccountMoveLineFixedDiscount) en verde
- [x] 4.2 Code review independiente (subagente `code-reviewer`, sin memoria de la conversación) encontró 3 hallazgos bloqueantes -- los tres corregidos y verificados con test de regresión dedicado
- [ ] 4.3 Sin tarea/ticket vinculado ni aval funcional -- toca cálculo fiscal y un documento impreso, pendiente antes de abrir PR
- [ ] 4.4 Traducciones `es_VE.po` sin regenerar (campos eliminados quedan huérfanos en el `.po`, campo nuevo sin traducir)
- [ ] 4.5 Reporte `report_freeform_document` no se renderizó de punta a punta con datos reales (solo se confirmó que el XML carga sin error al instalar el módulo)
