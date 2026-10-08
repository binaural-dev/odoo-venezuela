# Fix: la línea de pago cortaba el segundo monto con "…" (l10n_ve_pos)

## Why

Tarea 83148, hallazgo H10 de la prueba e2e del 01-oct-2026. La línea de pago de
un método foráneo muestra dos montos ("$ 70,00 / 56.233,80 Bs.F", desde
577284e59). La plantilla es una copia completa de la del core y conserva su
`.payment-infos` en una sola fila con `text-truncate`: el nombre (224 px) y los
montos (207 px) no caben en los 360 px de la columna de pagos, ni con la
pantalla a 1920 px, y el final se corta. Lo que se pierde es el monto en la otra
moneda: "Efectivo USD (Caja VES) $ 70,00 / 56.2…". `binaural_pos_multicurrency`
pinta su "caja / compañía" en el mismo `.payment-amount`, así que en sus cajas
(USD, EUR) pasaba con todos los métodos.

## What Changes

- **`static/src/overrides/screens/payment_line/payment_line.xml`** (líneas
  seleccionada y no seleccionada): `.payment-infos` deja `text-truncate` y pasa a
  `flex-wrap` con `column-gap-3` y `overflow-hidden`; el nombre va en
  `span.payment-name.text-truncate` (en la línea no seleccionada era texto
  suelto) y `.payment-amount` es `ms-auto text-end`. Cada monto va sin cortes
  (`span.text-nowrap`) y el segundo (" / …") en `d-inline-block text-nowrap`.
  Si todo cabe, la línea queda en una fila como antes; si no, los montos bajan
  completos a una segunda fila alineada a la derecha, y si el par tampoco cabe
  ahí se parte por el " / " (tres filas). Lo que se trunca, si hace falta, es el
  nombre; un monto nunca.
- `binaural_pos_multicurrency` (integra-addons, PR #2896) pinta sus propios pares
  en el mismo `.payment-amount` y lleva las mismas clases.

## Non-goals

- Cambiar los montos o su formato (H9 y sus signos van aparte).
- Las extensiones de `binaural_megasoft` y `l10n_ve_pos_igtf` sobre
  `point_of_sale.PaymentScreenPaymentLines`: como `payment_line.js` cambia la
  plantilla del componente por esta, probablemente no se pintan. Es previo y
  queda fuera de este change, pendiente de decidir si se registra como hallazgo.

## Impact

- Solo presentación; ningún monto ni asiento cambia.
- Una línea que no cabe ocupa dos filas en la columna de pagos.
- Tests: `static/tests/unit/payment_lines_layout.test.js` (hoot).
