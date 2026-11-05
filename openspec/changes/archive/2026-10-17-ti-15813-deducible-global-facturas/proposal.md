## Why

Se pidió un descuento global "deducible" (porcentaje o monto fijo) para facturas (con o sin impuestos), activable por configuración y repartido por línea como un descuento nativo (ticket #15813). Se separa en un módulo propio porque la funcionalidad puede crecer.

## What Changes

- Módulo nuevo `l10n_ve_deductible` (depende de `l10n_ve_accountant` y `l10n_ve_invoice`, auto-instalable): opción por compañía `use_deductible` y alcance `deductible_scope` (proveedor, cliente o ambas); en el documento, bajo "Términos y condiciones", `is_deductible`, tipo, valor y monto referencial (solo en porcentaje); validaciones de sin descuento previo y límites del valor (el deducible no se limita a líneas con impuestos exentos; por defecto aplica a facturas de cliente).
- Campos por línea `global_deductible_line_amount` (importe restado, monetario, solo en monto fijo; se propone proporcional y el usuario puede escribirlo a mano en borrador: la línea queda marcada en `global_deductible_manual`, conserva su importe y el resto se reparte entre las demás; la suma es siempre el monto ingresado y se valida al guardar el documento y al publicarlo) y `global_deductible_discount_percent` (porcentaje exacto usado por el cálculo de impuestos, valor interno en modo monto fijo y columna de solo lectura «Deducido (%)» solo en modo porcentaje). Cifras idénticas al descuento nativo (%) y a `discount_fixed`.
- Consistencia al vuelo en el formulario; herencia a notas de crédito, de débito (con líneas copiadas) y a la factura de reemplazo de "reversar y modificar"; multicompañía; filas "Subtotal sin deducible" y "Deducible" en los tres widgets y en el reporte de forma libre; traducción es_VE.
- `l10n_ve_accountant` (19.0.1.0.34): `_get_effective_discount_percent()` como única fuente del descuento de una línea para el cálculo de impuestos, el subtotal en moneda alterna, `company_currency_line_totals`, `detailed_amounts` y el apunte de líneas con precio incluido; `_get_base_line_sync_extra_fields()` para que `_sync_tax_lines` vigile campos propios de otros módulos.

## Impact

- Specs: `l10n_ve_deductible` (nuevo), `l10n_ve_accountant`.
- Tests: batería de reglas, paridad y flujos para proveedor y cliente, multicompañía, alcance, vistas y traducción; regresión de `l10n_ve_accountant` y `l10n_ve_invoice` sin cambios.
- Fuera de alcance: máquinas fiscales y factura digital (no leen el deducible).
