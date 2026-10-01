## 1. l10n_ve_invoice — bloquear confirmación con fecha futura

- [x] 1.1 `AccountMove._check_dates_not_in_future()`: valida `invoice_date`, `invoice_date_display` y `date` contra `fields.Date.context_today()` para todo documento con `is_invoice(include_receipts=True)` (todo `move_type` salvo `entry`)
- [x] 1.2 Invocado al inicio de `action_post()`, antes del guard de impuesto por línea existente
- [x] 1.3 No se agrega como `@api.constrains` -- el borrador con fecha futura se puede guardar, solo se bloquea al confirmar

## 2. Manifest, traducciones y tests

- [x] 2.1 Bump `l10n_ve_invoice` 19.0.1.0.23 → 19.0.1.0.24
- [x] 2.2 Traducciones `es_VE` para las 3 etiquetas de campo y el mensaje de error
- [x] 2.3 Tests de regresión en `test_future_date_action_post.py`: factura/NC/venta y factura/NC de compra con cada uno de los 3 campos en el futuro bloquean `action_post`; recibo de venta y de compra con fecha futura también bloquean; un asiento contable (`entry`) con fecha futura NO se bloquea; fecha de hoy postea bien; borrador con fecha futura se guarda sin error; una nota de débito (mismo `account.move`, `debit_origin_id`) hereda el guard sin cambios adicionales

## 3. Verificación

- [x] 3.1 Suite de `l10n_ve_invoice` corrida en `docker-odoo` (contenedor `odoo-binaural-19`, db descartable) -- 236 tests, 0 fallos/errores
