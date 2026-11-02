# Spec delta: pos-refund-foreign-sign

## ADDED Requirements

### Requirement: Los montos foráneos llevan el signo del monto local

El sistema SHALL guardar `pos.order.foreign_amount_total` con el signo de
`amount_total` y cada `pos.payment.foreign_amount` con el signo de su `amount`,
también en reembolsos y órdenes mixtas. El PdV SHALL calcular el total foráneo
de un reembolso con el signo del total local, de modo que las tasas derivadas
de él sean positivas. El servidor SHALL corregir el signo de un monto foráneo
que llegue invertido, conservando su magnitud, y SHALL dejar intactos los
montos foráneos en cero.

#### Scenario: Reembolso pagado con un método foráneo

- **GIVEN** una venta de 18.637,49 Bs (23,20 $) cobrada en Bs en una caja en Bs
- **WHEN** se reembolsa una unidad (−9.318,74 Bs) y se paga con el efectivo $
- **THEN** el pago guarda `amount` −9.318,74 y `foreign_amount` −11,60, y la
  orden `foreign_amount_total` −11,60

#### Scenario: Cierre con el neto del efectivo foráneo en reembolso

- **GIVEN** una sesión cuyo único movimiento del efectivo $ es ese reembolso
- **WHEN** se cuenta lo que hay en el cajón y se cierra la sesión
- **THEN** el esperado del cajón $ resta los 11,60 $, no hay diferencia de
  cierre y la sesión cierra sin error

#### Scenario: PdV con el bundle anterior

- **GIVEN** un PdV que todavía manda `foreign_amount` +11,60 con `amount`
  −9.318,74
- **WHEN** el servidor procesa la orden
- **THEN** guarda `foreign_amount` −11,60, y un pago con `foreign_amount` 0
  sigue en 0

#### Scenario: Orden mixta (reembolso más venta)

- **GIVEN** una orden con una línea reembolsada de 11,60 $ y una línea vendida
  de 5 $
- **WHEN** el PdV calcula el total foráneo
- **THEN** el total es −6,60 $

#### Scenario: Cajero teclea el monto foráneo en positivo en un reembolso

- **GIVEN** un reembolso de −3.600 Bs (−90 $) sin tasa exacta del pago original
- **WHEN** el cajero teclea 100 en el método foráneo
- **THEN** el pago queda con `foreign_amount` −100 y `amount` −4.000 Bs
  (deuda más el excedente de 10 $, ambos negativos)

#### Scenario: Devolución desde el backend

- **GIVEN** una devolución creada con "Devolver productos" y pagada con el
  wizard de pago, que copia el `foreign_amount_total` positivo de la original
- **WHEN** se procesa el pago
- **THEN** `foreign_amount_total` queda con el signo de `amount_total`
