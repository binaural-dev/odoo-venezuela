## Why

Se puede confirmar una factura, nota de crédito, nota de débito o recibo (de venta o de compra) con `invoice_date`, `invoice_date_display` o `date` (fecha contable) posteriores a la fecha del día. Fiscalmente un comprobante no puede llevar una fecha futura a la de su emisión/confirmación real. (Ticket #15450.)

## What Changes

- `l10n_ve_invoice`: nuevo guard `account.move._check_dates_not_in_future()`, invocado desde `action_post()` antes de cualquier otra validación de confirmación. Para cualquier documento que no sea un asiento contable puro (`move_type != 'entry'`, vía `is_invoice(include_receipts=True)` -- factura, nota de crédito, nota de débito y recibo, ambos lados, venta y compra), bloquea la confirmación si `invoice_date`, `invoice_date_display` o `date` es posterior a `fields.Date.context_today()`.
- Solo corre en `action_post`, no como `@api.constrains`: un borrador puede guardarse con fecha futura (por ejemplo, dejarlo preparado) sin bloquear el guardado -- el mismo patrón ya usado por el guard de impuesto obligatorio por línea en este archivo.
- Una nota de débito es un `account.move` normal con `debit_origin_id` (mismo `move_type` que su origen) -- el guard la cubre sin código adicional, porque pasa por el mismo `action_post`.
- Bump de manifest `l10n_ve_invoice` 19.0.1.0.23 → 19.0.1.0.24.
- Traducción `es_VE` agregada solo para el mensaje de error nuevo (`i18n/es_VE.po`). La etiqueta de cada campo (`%(field)s`) NO se hardcodea: se lee de `self.fields_get(field_names)[...]['string']`, el `string` real y ya traducido de ese campo en este modelo -- por ejemplo `invoice_date` está sobreescrito a "Rate Date" en `l10n_ve_accountant` (usado solo para la tasa de cambio, no "Invoice/Bill Date" de core), y el mensaje debe reflejar esa etiqueta tal cual la ve el usuario, no una inventada en el código del guard.

## Impact

- Specs afectadas: `l10n_ve_invoice` (nueva requirement).
- Código: `l10n_ve_invoice/models/account_move.py`, `l10n_ve_invoice/i18n/es_VE.po`.
- No afecta documentos de compra ya registrados con fecha pasada (el caso normal de una factura de proveedor recibida días después de emitida), ni bloquea guardar borradores -- solo bloquea confirmar con una fecha que todavía no ha llegado. Los asientos contables puros (`entry`) quedan fuera del alcance.
