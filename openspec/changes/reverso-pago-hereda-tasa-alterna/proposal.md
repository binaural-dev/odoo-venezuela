## Why

Al reintegrar/reembolsar el pago de una factura en una fecha posterior a su emisión, el asiento del reverso recalcula el monto en moneda alterna (USD) con la tasa del día del reverso en lugar de revertir exactamente el USD que quedó registrado en el pago original. Esto descuadra la moneda alterna del asiento del reintegro (ticket #15114).

La causa está en `account.move.line._get_foreign_rate_date()` (fuente única de fecha para todo cálculo de moneda alterna): para asientos que no son facturas devuelve la fecha contable del asiento, así que un reverso de pago (`move_type` `entry`) se valora a su propia fecha. El caso de Nota de Crédito ya quedaba correcto porque su `invoice_date` (fecha de tasa) se hereda del documento original, pero el reverso del asiento de un pago no tenía forma de heredar esa fecha. Es un problema de la capa base `l10n_ve_accountant`, por lo que afecta tanto a facturación normal como a PdV.

## What Changes

- `l10n_ve_accountant`: cuando el asiento tiene `reversed_entry_id` (NC/ND o reverso del asiento de un pago), `_get_foreign_rate_date()` valora la moneda alterna a la fecha de tasa del asiento ORIGINAL revertido, siguiendo la cadena de `reversed_entry_id` de forma recursiva. Así el reverso devuelve exactamente el importe alterno del original aunque la tasa haya cambiado entre ambas fechas.
- No se toca el `@api.depends` de `_compute_foreign_debit_credit`: el reverso se crea con `reversed_entry_id` ya en su `create`, y en un `create` los campos computed-stored se calculan igual (independiente de las dependencias). `reversed_entry_id` es inmutable tras crear, así que no aporta un disparo de recálculo nuevo.

## Impact

- Specs afectadas: `l10n_ve_accountant` (se MODIFICA la requirement "Débito y crédito alterno por apunte contable": la conversión de asientos no-factura usa la fecha de tasa del apunte, que en un reverso es la del asiento original).
- Código: `l10n_ve_accountant/models/account_move_line.py` (`_get_foreign_rate_date`, nuevo helper `_foreign_rate_date_for_move`, depends de `_compute_foreign_debit_credit`).
- Corrige por igual el reverso de pagos de facturas normales y de PdV. No cambia el comportamiento de la NC/ND (su `invoice_date` ya coincide con el del original), ni el cálculo de facturas/pagos que no son reversos.
