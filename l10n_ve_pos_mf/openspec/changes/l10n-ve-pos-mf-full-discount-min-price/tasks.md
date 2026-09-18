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
      como N × 0,01 + `discount_amount` (N − 1) × 0,01 (versión inicial:
      1 × 0,01, sin la cantidad real)
- [x] 2.3 `_applyGlobalDiscountBeforeValidation`: restaurar precios reales antes
      de inferir el % global
- [x] 2.4 `pay()`: respaldo que sustituye líneas en neto 0 antes del pago
- [x] 2.5 `_applyGlobalDiscountBeforeValidation`: calcular la base del monto
      informativo (`DESC. GLOBAL`) ANTES de `setDiscount`, que con el 100%
      sustituye el precio por 0,01 (salía Σ 0,01 × cantidad; review PR #1323)
- [x] 2.6 Cantidad fraccionaria (pesados): 1 × 0,01 con `CANT 1,25 KG -` en
      la descripción (`_mfFiscalMinProductName`)
- [x] 2.7 `l10n_ve_mf_base` `TfhkaDriver.printInvoice`: `q-<monto>` justo
      después del ítem si la línea trae `discount_amount > 0` + test unitario +
      bump `19.0.1.1.2`
- [x] 2.8 Nota de crédito:
      - `printCreditNote` envía `q-` tras el ítem (`_appendItemDiscount`,
        compartido con la factura).
      - `mfIsRefundOfFiscalMin()` marca las devoluciones de líneas de mínimo
        fiscal, incluida la de 2 unidades, sin recalcular el descuento.
- [x] 2.9 Flags 11/12: fuera del alcance (la caja y el driver sólo soportan
      00/01/02/30). Descartados por el usuario:
      - leer el flag con `S3` antes de imprimir, porque es lento;
      - avisar al teclear el 100%, porque nunca podía dispararse.
- [x] 2.10 Test unitario del driver: `q-` en nota de crédito (no corrido).

## 3. Metadatos

- [x] 3.1 Bump de versión del manifest `19.0.3.1.2` → `19.0.3.1.3`
- [x] 3.2 Documentación OpenSpec del cambio

## 4. Verificación (navegador 2026-09-15 — db vzla19_2doce)

- [x] 4.1 Reconstruir/servir assets (`-u l10n_ve_pos_mf`) + hard refresh
- [x] 4.2 Descuento **por línea** 100% con cantidad grande → subtotal de la
      línea 0,01 (probado qty 10 → 0,01), cantidad intacta, sin bloqueo
- [x] 4.3 Descuento **global** 100% → cada línea con subtotal 0,01, cantidad
      intacta (2026-09-18, caja C1-CCS, orden C1-CCS - 000003: 3 líneas × 2 uds
      → 0,01 c/u, total 0,03)
- [x] 4.4 Cambiar la cantidad tras la sustitución → subtotal sigue en 0,01
      (2026-09-18, caja C1-CCS)
- [ ] 4.5 Quitar/cambiar el descuento tras un 100% → precio original restaurado
- [x] 4.6 Descuento parcial (< 100%) → comportamiento idéntico al actual
      (2026-09-18, caja C1-CCS)
- [x] 4.7 Impresión en la MF (línea 1 × 0,01) y cierre `199` cuadra con el pago
      (2026-09-18, misma orden → factura fiscal 403 por 0,03)
- [x] 4.8 Descuento global 100% en la MF → `DESC. GLOBAL` muestra el total real
      de las líneas (antes del fix 2.5 imprimió 0,06 en la factura 403)
- [x] 4.9 Impresión en la MF → la línea de mínimo fiscal sale con su cantidad
      real (N × 0,01), el descuento `q-` sobre el ítem la deja en 0,01 y el
      cierre `199` cuadra
- [x] 4.10 Producto pesado (cantidad fraccionaria) al 100% → 1 × 0,01 con
      `CANT <cantidad> KG -` en la descripción
- [x] 4.11 Compatibilidad según el manual HKA V8.5.0: el flag 21 en
      00/01/02/30 funciona en todos los modelos de la tabla; en 11/12 no
      (ver design.md, "Compatibilidad con los modelos de MF").
- [x] 4.13 Nota de crédito de una orden con línea en el mínimo fiscal (2 y 10
      unidades) → la NC sale con la cantidad real, `q-` y total 0,01; el `199`
      cuadra.
      (4.8, 4.9, 4.10 y 4.13 probadas en la MF física de 2doce el 2026-09-18.)
- [ ] 4.12 Probar en una MF de cada familia (SRP-812/HKA-80/DT-230/PP9 y
      SRP-350/HKA-112/HSP7000/TD1125/KUBE):
      - `D` (flag 21 y firmware);
      - N = 2, 10 y 1000, en tasa G y en exento;
      - ACK, `199` y cómo se imprime la línea.
