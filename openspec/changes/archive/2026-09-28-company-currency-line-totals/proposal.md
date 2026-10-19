## Why

`price_unit_ves` (`l10n_ve_accountant`, `account.move.line`) convertía el precio unitario a la moneda de la compañía de forma independiente, sin garantía de reconciliar con el `balance` real del asiento -- podía diferir por el mismo redondeo cruzado que `_apply_product_real_portion`/`_distribute_final_real_portion` existen para corregir. Tampoco existía forma de obtener, por línea de factura, el desglose completo (subtotal, impuesto, descuento) en moneda de la compañía cuando la factura está en USD/EUR/otra moneda distinta.

## What Changes

- `l10n_ve_accountant`: elimina `account.move.line.price_unit_ves`/`ves_currency_id`. Agrega `account.move.company_currency_line_totals` (Json, store=True): por línea de producto, en moneda de la compañía -- `price_unit`, `quantity`, `subtotal`, `subtotal_taxed`, `tax_amount`, `discount_amount`, `discount_type`, `taxes` (id/name/price_include). `subtotal` sale del propio `balance` de la línea (ya exacto tras la corrección de real-portion); `tax_amount` reparte el `balance` de cada línea de impuesto entre las líneas de producto que la comparten, proporcional a su `balance`, con el mismo criterio de mayor-residuo que `_distribute_to_lines`; el signo sale de `price_subtotal`, no de un `abs()` ciego; los impuestos de tipo `group` se resuelven por su jerarquía aplanada.
- `l10n_ve_accountant`: migración `19.0.1.0.24` que dropea las columnas huérfanas `price_unit_ves`/`ves_currency_id`.
- `l10n_ve_invoice`: sobrescribe `_compute_company_currency_line_totals` para corregir el caso `discount_fixed` (que fuerza el `discount` nativo a 0), y actualiza el reporte `report_invoice_free_form` para usar el campo nuevo en la columna de precio unitario.
- Bump de manifest: `l10n_ve_accountant` 19.0.1.0.23 → 19.0.1.0.25, `l10n_ve_invoice` 19.0.1.0.21 → 19.0.1.0.23.

## Impact

- Specs afectadas: `l10n_ve_accountant` (nueva requirement "Desglose por línea de factura en moneda de la compañía"), `l10n_ve_invoice` (nueva requirement "Ajuste de descuento fijo en el desglose por línea en moneda de la compañía").
- Código: `l10n_ve_accountant/models/account_move.py`, `l10n_ve_accountant/models/account_move_line.py`, `l10n_ve_accountant/migrations/19.0.1.0.24/`, `l10n_ve_invoice/models/account_move.py`, `l10n_ve_invoice/report/report_invoice_free_form.xml`.
- No cambia el cálculo de impuestos en la moneda de la factura (`price_subtotal`/`price_total` nativos siguen igual); solo agrega la vista en moneda de la compañía y elimina el campo que reemplaza.
