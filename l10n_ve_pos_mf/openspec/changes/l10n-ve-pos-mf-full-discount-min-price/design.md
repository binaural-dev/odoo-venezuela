# Diseño

## Contexto y restricciones

- La MF imprime en Bs; el mínimo representable de una línea es **0,01**. El
  driver descarta `price_unit <= 0`.
- `account.move.line.discount` tiene precisión de **2 decimales** (decimal
  precision `Discount`). `pos.order.line.discount` es float sin límite, pero al
  facturar se copia a la línea contable y se redondea a 2 decimales.
- `_check_max_discount` (l10n_ve_accountant) bloquea `discount >= 100%` en
  cualquier `account.move.line` con producto.

De ahí que el 0,01 se realice como **precio** (`price_unit = 0,01`, `discount =
0`) y no como porcentaje: es la única forma de que el neto quede en 0,01 y la
factura no se bloquee, sin tocar `l10n_ve_accountant`.

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
   redondea a 0 y el precio base es > 0, guardar el precio original y fijar
   `precio 0,01 / descuento 0`.

El guard `_mf_fiscal_guard` evita recursión (las llamadas internas a
`setDiscount(0)`/`setUnitPrice` no vuelven a entrar en la lógica).
`setUnitPrice` es el override de `l10n_ve_pos`, que actualiza también
`foreign_price`.

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
