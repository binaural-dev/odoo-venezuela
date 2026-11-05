# Fix: la línea del PdV mostraba el monto en divisa SIEMPRE con impuesto, ignorando la config "impuesto separado" (l10n_ve_pos)

## Why

La plantilla `components/orderline/orderline.xml` (migrada de V17 en el commit
`88c9d34c1`) agrega el monto en divisa junto al precio local así:

```xml
/ <t t-out="env.utils.formatForeignCurrency(line.get_foreign_price_with_tax())"/>
```

Siempre usa `get_foreign_price_with_tax()` (precio CON impuesto), sin mirar la
configuración de visualización de impuestos del PdV
(`pos.config.iface_tax_included`). El core, en cambio, muestra el precio
LOCAL según esa config: `priceIncl` cuando es `'total'` (con impuesto) y
`priceExcl` cuando es `'subtotal'` (impuesto separado) — ver
`pos_order_line_accounting.js::displayPrice`.

Resultado: en un PdV configurado con "impuesto separado" (`subtotal`), la
columna local muestra el precio SIN impuesto pero la columna en divisa lo
muestra CON impuesto, y no cuadran (p. ej. local $8,62 vs divisa $10 por el
IVA). Bug preexistente, independiente del cálculo de tasa; es solo la
elección de qué monto convertir para mostrar.

## What Changes

- **`static/src/overrides/components/orderline/orderline.xml`**: el monto en
  divisa de la línea ahora espeja la config, igual que el core:
  - `iface_tax_included === 'total'` → `get_foreign_price_with_tax()`
  - en caso contrario (`'subtotal'`) → `get_foreign_price_without_tax()`

Ambos métodos ya existen en `pos_order_line.js` y comparten el mismo camino
de conversión (`_conv` → tasa viva, o tasa congelada en reembolsos), así que
la línea en divisa queda consistente con la local en cualquier config.

## Impact

- **Capability**: `pos-refund-original-rate` (extendida — mismo dominio del
  display foráneo por línea).
- **Módulo**: `l10n_ve_pos`, solo frontend (una plantilla). Fix **visual**;
  no toca cálculo de tasa ni contabilidad. Requiere recarga de assets del PdV.
- **Cambio de comportamiento visible**: con "impuesto separado", la línea en
  divisa pasa a mostrarse SIN impuesto, cuadrando con la columna local. Con
  "impuesto incluido" (`total`, el default) no cambia nada.
- **Riesgo**: bajo — el default `iface_tax_included = 'total'` conserva el
  comportamiento actual; solo cambia el caso `subtotal`.
