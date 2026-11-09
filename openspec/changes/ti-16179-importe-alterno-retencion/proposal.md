## Why

El importe alterno (`foreign_amount`) del pago de una retención se calculaba con `payment.date`, que es la fecha contable de la retención, mientras que las líneas de su asiento se valoran con la fecha de la factura retenida (`account.move.line._get_foreign_rate_date`). Con tasas distintas entre ambas fechas el campo quedaba distinto al monto alterno del asiento (ejemplo: 114,00 USD en el pago contra 120,00 USD en el asiento, con la tasa subiendo de 380 a 400) (ticket #16179).

## What Changes

- `l10n_ve_payment_extension`: nuevo `account.payment._get_retention_foreign_rate_date()`, única regla de la fecha de tasa de una retención (fecha de la factura cuando todas las líneas del pago pertenecen a una sola factura). El override de `account.move.line._get_foreign_rate_date` delega en ella, para que el asiento y el pago no puedan diverger.
- `account.payment._compute_foreign_amount` convierte con esa fecha para pagos de retención; depende además de `is_retention` y `retention_line_ids.move_id`, porque el pago se crea sin líneas y estas se asocian después.
- La fecha contable del pago y de su asiento no cambia. Los pagos que no son retención conservan el cálculo por `payment.date`.

## Impact

- Specs afectadas: `l10n_ve_payment_extension` (nuevo requisito: el importe alterno del pago de una retención usa la fecha de tasa de su asiento).
- Código: `l10n_ve_payment_extension/models/account_payment.py`, `models/account_move_line.py`. Versión del manifest 19.0.2.2.6.
- Los pagos de retención ya publicados conservan el valor guardado; este cambio no los recalcula (no hay migración).
