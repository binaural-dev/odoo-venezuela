# Diseño

## Contexto y restricciones

- La MF imprime en Bs; el mínimo representable de una línea es **0,01**. El
  driver descarta `price_unit <= 0`.
- `account.move.line.discount` tiene precisión de **2 decimales** (decimal
  precision `Discount`). `pos.order.line.discount` es float sin límite, pero al
  facturar se copia a la línea contable y se redondea a 2 decimales.
- `_check_max_discount` (l10n_ve_accountant) bloquea `discount >= 100%` en
  cualquier `account.move.line` con producto.

El requisito es que la **línea completa** (subtotal, no 0,01 por unidad) quede
en 0,01 conservando la cantidad. Con 2 decimales no se puede con un precio
unitario fraccionario (0,01/qty → 0,00). Se fija entonces `price_unit = 0,01` y
`discount = (1 − 1/qty) × 100`, de modo que subtotal = 0,01 × qty × (1/qty) =
0,01, con el descuento < 100% (no lo bloquea `_check_max_discount`) y el precio
> 0. La MF (precio × cantidad, 2 decimales) no puede repartir 0,01 entre N
unidades, así que esas líneas se le envían como **1 × 0,01**.

## Punto de intercepción único: `PosOrderline.setDiscount`

Todos los caminos de descuento terminan en `line.setDiscount(val)`:

- Descuento **por línea** (numpad `%`): `OrderSummary` → `pos.setDiscountFromUI`
  (gateado por `binaural_pos_hr`) → `line.setDiscount`.
- Descuento **global** (`pos_discount`): `_applyGlobalDiscountBeforeValidation`
  convierte el global a descuento por línea con `line.setDiscount(inferred)`.

Por eso el patch a `setDiscount` cubre ambos con una sola pieza.

### Algoritmo de `setDiscount`

1. Si el guard de re-entrada está activo, delegar directo al core.
2. `mfRestoreOriginalPrice()`: si la línea fue sustituida antes, restaurar su
   precio real (para evaluar el nuevo descuento sobre la base verdadera).
3. `super.setDiscount(discount)` (el core clampa a `[0, 100]`).
4. `mfEnsureNonZeroFiscalPrice()`: si con el descuento aplicado el neto
   redondea a 0 y el precio base es > 0, guardar el precio original, marcar
   `_mf_fiscal_min` y llamar a `_mfApplyLineFiscalMin()` (precio 0,01 +
   descuento (1−1/qty)×100 → subtotal 0,01).

El guard `_mf_fiscal_guard` evita recursión (las llamadas internas a
`setDiscount`/`setUnitPrice` no vuelven a entrar en la lógica). `setUnitPrice`
es el override de `l10n_ve_pos`, que actualiza también `foreign_price`.

### Cambio de cantidad y envío a la MF

- `setQuantity`: si la línea es `_mf_fiscal_min`, tras aplicar la cantidad se
  vuelve a llamar a `_mfApplyLineFiscalMin()` para recalcular el descuento y
  mantener el subtotal en 0,01 con la nueva cantidad.
- `PosStore.get_data_invoice` propaga `_mf_fiscal_min` a cada línea del payload;
  `_convertOrderForDriver` envía esas líneas a la MF como **1 × 0,01** (única
  forma de que la línea fiscal sume 0,01 y el cierre `199` cuadre con el pago,
  ya que la MF trabaja el precio unitario con 2 decimales).

## Interacción con el descuento global (Estrategia A)

`_applyGlobalDiscountBeforeValidation` **infiere** el porcentaje global a partir
de los precios de línea. Si una línea quedó sustituida a 0,01 en una aplicación
anterior, la inferencia usaría 0,01 como base y daría un porcentaje erróneo. Por
eso, antes de inferir (y sólo cuando se va a re-aplicar, tras los early-returns),
se restauran los precios reales con `mfRestoreOriginalPrice()`. El caso de
finalización (`finalizeValidation`) hace early-return cuando el global ya está
aplicado, así que **no** deshace la sustitución.

## Respaldo en `pay()`

El caso normal se resuelve al **aplicar** el descuento (paso 4). El respaldo en
`PosStore.pay()` recorre las líneas y aplica `mfEnsureNonZeroFiscalPrice()`
antes de mostrar el pago, para cubrir órdenes cargadas/reanudadas cuyas líneas
ya venían con 100% (donde `setDiscount` nunca se invocó en esta sesión).

## Reversibilidad

`_mf_zeroed_original_price` guarda el precio de lista. Cualquier `setDiscount`
posterior (incluido `setDiscount(0)` al quitar el descuento, o el
`_resetGlobalDiscountOnLines` del global) restaura el precio antes de aplicar el
nuevo valor, dejando la línea como si nunca se hubiera sustituido.

## Alternativas descartadas

- **Capar el porcentaje** para dejar neto 0,01: inviable por la precisión de 2
  decimales del descuento en factura (redondea a 100% → re-bloquea).
- **Sólo hacer floor en el payload de la MF**: la MF imprimiría 0,01 pero la
  orden/factura seguiría en 0,00 con 100% → la bloquearía `_check_max_discount`
  y el cierre `199` no cuadraría con el pago (0,00 vs 0,01).
- **Relajar `_check_max_discount`**: fuera del alcance (vive en
  `l10n_ve_accountant`, no en un módulo de MF).
