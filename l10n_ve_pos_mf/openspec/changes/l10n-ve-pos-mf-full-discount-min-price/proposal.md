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
el mínimo fiscal **0,01** en lugar de bloquearse.

Nota de diseño: **no se puede** lograr el 0,01 bajando el porcentaje de
descuento, porque el campo `discount` de la factura sólo admite **2 decimales**
— el descuento necesario (p. ej. 99,9998% para un ítem de Bs 4.816) se
redondearía a 100,00% y volvería a disparar el bloqueo. Por eso el 0,01 se
realiza como **precio de línea**, no como porcentaje.

## What Changes

Todo dentro de `l10n_ve_pos_mf` (sólo PdV; no se toca `l10n_ve_account_mf` ni
`l10n_ve_accountant`).

- **`overrides/PosOrderline.js` (nuevo):** patch de `PosOrderline.setDiscount`.
  Cuando el descuento resultante dejaría el neto de la línea en 0 (con precio
  base > 0), se sustituye la línea por **precio unitario 0,01 y descuento 0**,
  guardando el precio original en `_mf_zeroed_original_price`. Si luego se
  cambia o se quita el descuento, se **restaura** el precio original antes de
  evaluar el nuevo valor (revertible). `setDiscount` es el punto por el que
  pasan tanto el descuento por línea (numpad → `pos.setDiscountFromUI` →
  `line.setDiscount`) como el global (`_applyGlobalDiscountBeforeValidation` →
  `line.setDiscount`), de modo que un solo patch cubre ambos casos.
- **`overrides/PosStore.js`:**
  - `_applyGlobalDiscountBeforeValidation`: antes de **inferir** el porcentaje
    global, se restauran los precios reales de las líneas que hubieran sido
    sustituidas por 0,01 en una aplicación previa, para que la inferencia no
    use 0,01 como base.
  - `pay()` (respaldo): antes de ir a la pantalla de pago se recorren las
    líneas y se aplica la sustitución a las que estén en neto 0, de modo que el
    total y el pago ya reflejen 0,01. Cubre además órdenes cargadas/reanudadas
    cuyas líneas ya venían con descuento 100%.

Resultado: la línea queda en 0,01 al **aplicar** el descuento (el cajero ve y
cobra 0,01), la MF imprime la línea, y la factura generada lleva `discount = 0`
→ no la bloquea `_check_max_discount`. Fiscal = contabilidad = 0,01.

## Capabilities

### Added Capabilities

- `pos-mf-full-discount-min-price`: invariante de que ninguna línea de una
  orden de PdV con máquina fiscal llegue a la impresión fiscal ni a la factura
  con neto 0,00 por efecto de un descuento del 100%; en ese caso se factura en
  el mínimo fiscal 0,01 sin descuento, de forma revertible.

## Impact

- Módulo: `l10n_ve_pos_mf` (`static/src/overrides/PosOrderline.js` nuevo,
  `static/src/overrides/PosStore.js`). Versión `19.0.3.1.2` → `19.0.3.1.3`.
- Sin cambios de datos, modelos Python ni dependencias. Asset estático:
  requiere reconstruir/servir los assets (o `--dev=all` + hard refresh) para
  verlo.
- No se modifica la validación `_check_max_discount` ni ningún módulo fuera de
  `l10n_ve_pos_mf`. Para descuentos < 100% el comportamiento es idéntico al
  actual.
