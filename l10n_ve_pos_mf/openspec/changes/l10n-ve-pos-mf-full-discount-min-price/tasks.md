## 1. Sustitución en la orderline

- [x] 1.1 `overrides/PosOrderline.js`: patch de `setDiscount` que, si el neto
      quedaría en 0 (precio base > 0), factura la línea en el mínimo fiscal
      (precio 0,01 + descuento (1−1/qty)×100 → subtotal 0,01, cantidad intacta),
      guardando el precio original y marcando `_mf_fiscal_min`
- [x] 1.2 `setQuantity`: recalcular el descuento de las líneas `_mf_fiscal_min`
      para mantener el subtotal en 0,01 al cambiar la cantidad
- [x] 1.3 `mfRestoreOriginalPrice()` / `_mfApplyLineFiscalMin()` con guard de
      re-entrada (`_mf_fiscal_guard`); revertible al cambiar/quitar el descuento
- [x] 1.4 Cubrir descuento por línea (numpad) y global (mismo `setDiscount`)

## 2. Ajustes en PosStore

- [x] 2.1 `get_data_invoice`: propagar `_mf_fiscal_min` a las líneas del payload
- [x] 2.2 `_convertOrderForDriver`: enviar las líneas `_mf_fiscal_min` a la MF
      como 1 × 0,01 (la MF no puede repartir 0,01 entre N unidades)
- [x] 2.3 `_applyGlobalDiscountBeforeValidation`: restaurar precios reales antes
      de inferir el % global
- [x] 2.4 `pay()`: respaldo que sustituye líneas en neto 0 antes del pago

## 3. Metadatos

- [x] 3.1 Bump de versión del manifest `19.0.3.1.2` → `19.0.3.1.3`
- [x] 3.2 Documentación OpenSpec del cambio

## 4. Verificación (navegador 2026-09-15 — db vzla19_2doce)

- [x] 4.1 Reconstruir/servir assets (`-u l10n_ve_pos_mf`) + hard refresh
- [x] 4.2 Descuento **por línea** 100% con cantidad grande → subtotal de la
      línea 0,01 (probado qty 10 → 0,01), cantidad intacta, sin bloqueo
- [ ] 4.3 Descuento **global** 100% → cada línea con subtotal 0,01, cantidad
      intacta
- [ ] 4.4 Cambiar la cantidad tras la sustitución → subtotal sigue en 0,01
- [ ] 4.5 Quitar/cambiar el descuento tras un 100% → precio original restaurado
- [ ] 4.6 Descuento parcial (< 100%) → comportamiento idéntico al actual
- [ ] 4.7 Impresión en la MF (línea 1 × 0,01) y cierre `199` cuadra con el pago
