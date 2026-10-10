## 1. l10n_ve_invoice — bloquear confirmación con fecha futura

- [x] 1.1 `AccountMove._check_dates_not_in_future()`: valida `invoice_date_display` contra `fields.Date.context_today()` y `invoice_date` contra `invoice_date_display` (`date` no se valida) para todo documento con `is_invoice(include_receipts=True)` (todo `move_type` salvo `entry`)
- [x] 1.2 Invocado al inicio de `action_post()`, antes del guard de impuesto por línea existente
- [x] 1.3 No se agrega como `@api.constrains` -- el borrador con fecha futura se puede guardar, solo se bloquea al confirmar

## 2. Manifest, traducciones y tests

- [x] 2.1 Bump `l10n_ve_invoice` 19.0.1.0.23 → 19.0.1.0.24
- [x] 2.2 Traducción `es_VE` de los dos mensajes de error (las etiquetas de campo ya vienen traducidas de `fields_get`)
- [x] 2.3 Tests de regresión en `test_future_date_action_post.py`: factura/NC/venta y factura/NC de compra con `invoice_date_display` o `invoice_date` fuera de regla bloquean `action_post`; recibo de venta y de compra con fecha futura también bloquean; un asiento contable (`entry`) con fecha futura NO se bloquea; fecha de hoy postea bien; borrador con fecha futura se guarda sin error; una nota de débito (mismo `account.move`, `debit_origin_id`) hereda el guard sin cambios adicionales

## 3. Verificación

- [x] 3.1 Suite de `l10n_ve_invoice` corrida en `docker-odoo` (contenedor `odoo-binaural-19`, db descartable) -- 236 tests, 0 fallos/errores
- [x] 1.4 `l10n_ve_donation`: la NC de reverso usa `context_today` en lugar de `fields.Date.today()`
- [x] 1.5 `l10n_ve_donation`: `_reverse_moves` también usa `context_today` en el valor por defecto de `date`
- [x] 1.6 `l10n_ve_exchange_difference` (tests): fechas futuras pasadas a 2000-2019; el wizard estándar de reversión usa la fecha de la nota; el diario VEF reutilizado debe tener cuenta de pago entrante
- [x] 2.4 Bump `l10n_ve_exchange_difference` 19.0.0.0.4 → 19.0.0.0.5 y `l10n_ve_donation` 19.0.2.0.4 → 19.0.2.0.5
- [x] 3.2 Verificado en contenedor aparte con base nueva sin demo: `l10n_ve_invoice` (17 tests) y `l10n_ve_exchange_difference` (77 tests), con `l10n_ve_donation` instalado, sin fallos

