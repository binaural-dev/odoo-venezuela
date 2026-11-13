## Why

La fórmula del monto de la retención de IVA estaba escrita dos veces en la localización (`compute_retention_lines_data` y `_apply_iva_tax_group_values`) y copiada en `binaural_mobile` (controlador y JavaScript): un cambio de regla no llegaba a los portales. La regla de tolerancia de redondeo entre monedas también necesitaba un único lugar para que el cierre de facturas y los portales decidan igual (ticket #16185).

## What Changes

- `account.retention.compute_iva_retention_amount(monto_impuesto, porcentaje)`: único cálculo del monto de la retención de IVA; lo usan la carga de líneas y la línea de retención, y los portales con su propio porcentaje.
- `account.move._retention_amount_tolerance()` (regla 1) y `_retention_max_accepted_difference()` (regla 2, con tope): únicos límites de la regla de redondeo entre monedas; `_retention_difference_within_currency_precision` decide con ellos, convirtiendo con `_convert()` a la fecha del documento.
- No se tocan los valores alternos `foreign_*` de las líneas de retención (heredados, no se usan).

## Impact

- Specs afectadas: `l10n_ve_payment_extension` (nuevo requisito de cálculo único y tolerancia).
- Código: `models/account_retention.py`, `models/account_retention_line.py`, `models/account_move.py`.
- `binaural_mobile` (integra-addons) consume ambos métodos en un PR aparte.
- El redondeo entre monedas solo aplica con compañía en bolívar (`is_venezuelan_bolivar()`); las cuentas de diferencial salen de `move.company_id`.
- Por qué `_convert()` a la fecha del documento y no `invoice_currency_rate`: la fecha de la tasa es la fuente de verdad de todo el motor, que convierte con `_convert()` en muchos lugares; una excepción solo en retenciones lo haría inconsistente. Si la tasa de esa fecha cambia tras confirmar, el proceso es regresar la factura a borrador y volver a fijar la fecha para que recalcule (de lo contrario los pagos del mismo día generan diferenciales cambiarios erróneos); es un tema de proceso de la empresa, no del código.
