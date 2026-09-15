## 1. Sustitución en la orderline

- [x] 1.1 Nuevo `overrides/PosOrderline.js`: patch de `setDiscount` que, si el
      neto quedaría en 0 (precio base > 0), fija `precio 0,01 / descuento 0`
      guardando el precio original (`_mf_zeroed_original_price`)
- [x] 1.2 `mfRestoreOriginalPrice()` / `mfEnsureNonZeroFiscalPrice()` con guard
      de re-entrada (`_mf_fiscal_guard`) para evitar recursión
- [x] 1.3 Cubrir descuento por línea (numpad) y global (mismo `setDiscount`)

## 2. Ajustes en PosStore

- [x] 2.1 `_applyGlobalDiscountBeforeValidation`: restaurar precios reales antes
      de inferir el % global (evita usar 0,01 como base al re-aplicar)
- [x] 2.2 `pay()`: respaldo que sustituye líneas en neto 0 antes del pago
      (órdenes cargadas/reanudadas)

## 3. Metadatos

- [x] 3.1 Bump de versión del manifest `19.0.3.1.2` → `19.0.3.1.3`
- [x] 3.2 Documentación OpenSpec del cambio

## 4. Verificación (navegador, 2026-09-13 — db vzla19_2doce)

- [x] 4.1 Reconstruir/servir assets (`-u l10n_ve_pos_mf`) + hard refresh
- [x] 4.2 Descuento **por línea** 100% → la línea pasa a 0,01, total 0,01 y la
      orden no se bloquea (ya no salta "Discounts of 100%…")
- [x] 4.3 Descuento **global** 100% → todas las líneas a 0,01, mismo resultado
- [ ] 4.4 Quitar/cambiar el descuento tras un 100% → el precio original se
      restaura (revertible)
- [x] 4.5 Descuento parcial (< 100%) → comportamiento idéntico al actual
- [x] 4.6 Impresión en la MF y cierre `199` cuadra con el pago (0,01)
