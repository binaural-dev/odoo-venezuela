## Why

En el PdV con máquina fiscal, aplicar un descuento del **100%** (por línea o
global) deja el neto de la línea en **Bs 0,00**. Eso rompe por dos lados:

1. **La máquina fiscal no acepta líneas en 0,00.** El driver TFHKA
   (`l10n_ve_mf_base/TfhkaDriver.js`) descarta silenciosamente cualquier línea
   con `price_unit <= 0` (`if (linePrice <= 0) continue;`), por lo que la
   factura fiscal saldría **sin esa línea**.
2. **La factura queda bloqueada.** La validación `_check_max_discount`
   (`l10n_ve_accountant`) impide confirmar cualquier factura con `discount >=
   100%`. Reproducido en 2doce: la orden llega a la pantalla de pago en 0,00 y
   al validar salta *"Discounts of 100% or higher are not allowed on invoices"*.

El ticket define que, para la máquina fiscal, estas ventas deben facturarse en
el mínimo fiscal **0,01** por la LÍNEA COMPLETA (no 0,01 por unidad), en lugar
de bloquearse, y conservando la cantidad.

Nota de diseño: con precios de **2 decimales** no se puede dejar el subtotal en
0,01 con un precio unitario fraccionario (0,01/qty redondea a 0). Se fija
entonces **precio unitario 0,01 + descuento = (1 − 1/qty) × 100**, de modo que
subtotal = 0,01 × qty × (1/qty) = **0,01 exacto**, con el descuento por debajo
de 100% (no lo bloquea `_check_max_discount`) y el precio > 0. La máquina fiscal
(precio × cantidad, 2 decimales) no puede repartir 0,01 entre N unidades con
el precio, así que esas líneas se le envían como **N × 0,01 con un descuento
por monto de (N − 1) × 0,01 sobre el ítem** para que la línea fiscal sume 0,01,
el cierre `199` cuadre con el pago y la MF muestre la cantidad real.

## What Changes

`l10n_ve_pos_mf` (PdV) y el driver de `l10n_ve_mf_base`. No se toca
`l10n_ve_account_mf` ni `l10n_ve_accountant`.

- **`overrides/PosOrderline.js` (nuevo):** patch de `PosOrderline.setDiscount` y
  `setQuantity`. Cuando el descuento dejaría el neto de la línea en 0 (con
  precio base > 0), la línea se factura en el mínimo fiscal: precio 0,01 +
  descuento (1 − 1/qty) × 100 → subtotal 0,01 con la cantidad intacta, marcando
  la línea con `_mf_fiscal_min`. Con cantidad < 0,5 (pesados) el precio sube
  al céntimo siguiente de 0,01 / cantidad, sin descuento. Se guarda el precio
  original en `_mf_zeroed_original_price` (revertible), se recalculan precio y
  descuento si cambia la cantidad (`setQuantity`), y se fija
  `price_type = "manual"`. `mfIsFiscalMinLine()` reconoce además la línea por
  sus datos (sobrevive a recargar la caja y a reimprimir pedidos pendientes), y
  `setUnitPrice` la desmarca si se cambia el precio a mano. `setDiscount`
  es el punto por el que pasan el descuento por línea (numpad →
  `pos.setDiscountFromUI` → `line.setDiscount`) y el global
  (`_applyGlobalDiscountBeforeValidation` → `line.setDiscount`).
- **`overrides/PosStore.js`:**
  - `get_data_invoice`: propaga `_mf_fiscal_min` a las líneas del payload.
  - `_convertOrderForDriver`: las líneas `_mf_fiscal_min` se envían a la MF como
    `N × 0,01` con `discount_amount = (N − 1) × 0,01` (cantidad fraccionaria:
    `1 × 0,01` con `CANT <cantidad> <unidad> -` en la descripción).
  - `_applyGlobalDiscountBeforeValidation`: en la aplicación manual usa el
    porcentaje tecleado (`expectedPercent`) en vez del inferido del monto de
    `pos_discount`, que falla con líneas en el mínimo fiscal.
  - `pay()` (respaldo): antes de ir al pago se recorren las líneas y se aplica la
    sustitución a las que quedaron en neto 0 (órdenes cargadas/reanudadas).
- **`overrides/PosOrderline.js`:** `mfIsRefundOfFiscalMin()` reconoce la
  devolución de una línea de mínimo fiscal (original con precio 0,01 y
  descuento) y la marca sin recalcular el descuento.
- **`l10n_ve_mf_base` (`TfhkaDriver`):**
  - `_appendItemDiscount`: si la línea trae `discount_amount > 0`, envía
    `q-<monto>` justo después del ítem, en factura y nota de crédito.
  - Tests unitarios y bump `19.0.1.1.1` → `19.0.1.1.2`.

Resultado: el subtotal de la línea queda en **0,01** conservando la cantidad
(el cajero ve N unidades y cobra 0,01), la factura lleva descuento < 100% (no la
bloquea `_check_max_discount`) y la MF recibe la línea como N × 0,01 con
descuento (N − 1) × 0,01, mostrando la cantidad real. Fiscal y
contabilidad cuadran en 0,01.

## Capabilities

### Added Capabilities

- `pos-mf-full-discount-min-price`: invariante de que ninguna línea de una
  orden de PdV con máquina fiscal llegue a la impresión fiscal ni a la factura
  con neto 0,00 por efecto de un descuento del 100%; en ese caso la línea
  completa se factura en el mínimo fiscal 0,01 (conservando la cantidad), de
  forma revertible.

## Impact

- Módulo: `l10n_ve_pos_mf` (`static/src/overrides/PosOrderline.js` nuevo,
  `static/src/overrides/PosStore.js`). Versión `19.0.3.1.2` → `19.0.3.1.3`.
- Sin cambios de datos, modelos Python ni dependencias. Asset estático:
  requiere reconstruir/servir los assets (o `--dev=all` + hard refresh) para
  verlo.
- No se modifica la validación `_check_max_discount` ni ningún módulo fuera de
  `l10n_ve_pos_mf`. Para descuentos < 100% el comportamiento es idéntico al
  actual.
