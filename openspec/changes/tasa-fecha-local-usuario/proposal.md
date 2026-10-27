## Why

A partir de las 8 pm en Venezuela (UTC-4) los documentos fallan con "No hay una tasa asignada para USD al <día siguiente>". La fecha de respaldo de la tasa se calcula en UTC (`fields.Date.today()`, o `.date()` sobre un Datetime almacenado en UTC como `date_order`), y a esa hora la fecha UTC ya es la del día siguiente. Como `compute_rate` busca la tasa solo en la fecha exacta, pide una tasa que todavía no se ha cargado.

## What Changes

- `l10n_ve_accountant` (`account.move`): `default_rate`, `default_inverse_rate`, el `create` y `_compute_rate_for_documents` usan `fields.Date.context_today` como fecha de respaldo en lugar de `fields.Date.today()`.
- `l10n_ve_accountant` (`account.payment`): `_compute_rate` y `_compute_other_rate` usan `fields.Date.context_today` cuando el pago no tiene fecha.
- `l10n_ve_sale` (`sale.order`): nuevo `_l10n_ve_rate_date()`, que convierte `date_order` a la fecha local del usuario (`fields.Datetime.context_timestamp`). Lo usan `create`, `_compute_rate` y la confirmación; los defaults de tasa usan `fields.Date.context_today`.
- El `create` de `account.move` consulta la tasa de `invoice_date` o, si no hay, la de hoy en todos los asientos (también los de depreciación de activos): esa fecha de respaldo pasa a ser la local, de modo que crear asientos después de las 8 pm no pide la tasa del día siguiente.
- Las fechas explícitas del documento (`invoice_date`, `date`, `payment_date`) no se modifican.

## Impact

- Specs afectadas: `l10n_ve_accountant` (MODIFICA "Cálculo automático de la tasa según la fecha del documento") y `l10n_ve_sale` (MODIFICA "Moneda alterna y tasa por defecto en la orden", "Recálculo de tasa condicionado por configuración" y "Confirmación requiere tasa de moneda alterna").
- Código: `l10n_ve_accountant/models/account_move.py`, `l10n_ve_accountant/models/account_payment.py`, `l10n_ve_sale/models/sale_order.py`.
- Solo cambia el comportamiento entre las 8 pm y la medianoche (hora local), cuando la fecha local y la UTC difieren. No recalcula registros existentes.
- Depende de que el usuario tenga zona horaria configurada (`America/Caracas`): sin `tz`, `context_today` devuelve la fecha UTC y el comportamiento queda igual que antes (procesos sin usuario interactivo, como cron o controladores públicos).
