## Why

Con la base efectivo activa, el asiento IMBEF que el core genera al conciliar el pago de una factura copia el `display_type = 'tax'` de la factura, pero sus líneas nacen con `foreign_balance = 0`. El paso 1 de `account.move.line._get_foreign_value` devolvía ese valor sin mirar `amount_currency`, así que las dos líneas de impuesto del asiento (IVA por declarar y débito fiscal) quedaban con el monto alterno en 0, mientras las líneas base sí lo calculaban (ticket #16240). Es el mismo error que se corrigió en v17 con el ticket #10703 y no se pasó a 19.0.

## What Changes

- `l10n_ve_accountant`: `account.move.line._get_foreign_value` ya no usa el atajo de `foreign_balance` para líneas `tax` o `payment_term` de asientos con `tax_cash_basis_origin_move_id` (asientos de base efectivo). Esas líneas se valoran por la ruta de asientos que no son factura: `amount_currency` si la línea está en la moneda alterna, o conversión con la tasa.
- Facturas y demás asientos conservan el cálculo actual.
- Prueba `TestCashBasisForeign` (con `Form`): factura, pago, asiento IMBEF, pago parcial y la migración. En `l10n_ve_payment_extension`, prueba del cobro con retención de IVA sobre una factura en bolívares.

## Impact

- Specs afectadas: `l10n_ve_accountant` (nuevo requisito: el asiento de base efectivo trae el monto alterno en todas sus líneas).
- Código: `l10n_ve_accountant/models/account_move_line.py`. Versión del manifest 19.0.1.0.43.
- Migración `19.0.1.0.43/post-10-caba_tax_lines_foreign_amount.py`: recalcula las líneas de impuesto de los IMBEF existentes que quedaron con el alterno en 0 (idempotente; no toca las que ya lo tienen).
