## Why

La fórmula del monto de la retención de IVA estaba escrita dos veces en la localización (`compute_retention_lines_data` y `_apply_iva_tax_group_values`) y copiada en `binaural_mobile` (controlador y JavaScript): un cambio de regla no llegaba a los portales. La regla de tolerancia de redondeo entre monedas también necesitaba un único lugar para que el cierre de facturas y los portales decidan igual (ticket #16185).

## What Changes

- `account.retention.compute_iva_retention_amount(monto_impuesto, porcentaje)`: único cálculo del monto de la retención de IVA; lo usan la carga de líneas y la línea de retención, y los portales con su propio porcentaje.
- `account.move._retention_amount_tolerance()`: único lugar de la regla de tolerancia (el mayor paso de la moneda de compañía que, reconvertido a la moneda del documento, redondea a cero). `_retention_difference_within_currency_precision` la usa.
- No se tocan los valores alternos `foreign_*` de las líneas de retención (heredados, no se usan).

## Impact

- Specs afectadas: `l10n_ve_payment_extension` (nuevo requisito de cálculo único y tolerancia).
- Código: `models/account_retention.py`, `models/account_retention_line.py`, `models/account_move.py`.
- `binaural_mobile` (integra-addons) consume ambos métodos en un PR aparte.
