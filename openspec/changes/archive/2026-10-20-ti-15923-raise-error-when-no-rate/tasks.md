## 1. l10n_ve_rate — error cuando no hay tasa

- [x] 1.1 `compute_rate`: `raise_if_not_found=True` por defecto; `UserError` con moneda y fecha
- [x] 1.2 Moneda principal sin registro de tasa devuelve `1.0/1.0`; sin moneda devuelve `{}`
- [x] 1.3 `compute_inverse_rate`: `UserError` con tasa `0`, `None` o `False`
- [x] 1.4 Traducción es_VE y bump `l10n_ve_rate` 1.3 → 1.4

## 2. Tests

- [x] 2.1 `l10n_ve_rate/tests/test_res_currency_rate.py`: error por defecto (fecha anterior a todas las tasas, sin tasas, sucursal sin tasa en la jerarquía, compañía ajena), `raise_if_not_found=False` devuelve `{}`, moneda principal = 1.0, sin moneda = `{}`, `compute_inverse_rate` sin tasa
- [x] 2.2 `l10n_ve_accountant/tests/test_indexed_payments.py` y `test_account_journal_bank_account.py`: cargan la tasa de USD necesaria

## 3. Verificación

- [x] 3.1 BD nueva con demo, contenedor `proj`, `--addons-path` con `vertical3/odoo-venezuela` al inicio y puertos distintos al del servidor: `-u l10n_ve_rate,l10n_ve_accountant --test-tags /l10n_ve_rate,/l10n_ve_accountant`. `l10n_ve_rate`: 28 tests sin fallos. `l10n_ve_accountant`: 362 tests; los mismos 13 fallos que sin el cambio (entorno de la BD nueva: moneda VEF inactiva, diarios de banco sin cuenta, impuestos por defecto del plan contable), ninguno por tasas.
- [ ] 3.2 `l10n_ve_sale` no se pudo probar: instalarlo con demo en BD nueva falla (`Expected singleton: res.currency()`) también sin este cambio. Pendiente correrlo en el entorno del CI.
