# Spec delta: pos-refund-original-rate

## ADDED Requirements

### Requirement: La línea de pago foránea de un reembolso espeja al centavo el pago original

El sistema SHALL valorar en moneda principal una línea de `pos.payment` con
método `is_foreign_currency` de una orden de reembolso usando la tasa EXACTA
del tender foráneo de la orden original —`Σ|amount| / Σ|foreign_amount|` de
los pagos foráneos originales, expuesta por
`pos.order.get_refund_foreign_rate` y precargada por la pantalla de pago— de
modo que la conversión `foráneo → local` sea `|foráneo| × tasa_exacta`
(directa, espeja el pago original), con el signo del reembolso (monto y
`foreign_amount` negativos). El sistema SHALL fijar en cambio la deuda local
exacta (snap) solo cuando el monto foráneo tecleado apenas cubre la deuda
(diferencia dentro de un paso de redondeo foráneo convertido a local). El
sistema SHALL usar `1 / tasa_exacta` como `foreign_rate` enviado al servidor.
Cuando no exista tasa exacta (venta, o reembolso sin tender foráneo
original, o fallo del RPC), el sistema SHALL conservar el comportamiento
anterior sin cambios.

#### Scenario: Reembolso que teclea el mismo monto foráneo del pago original

- **GIVEN** una orden de reembolso cuya orden original tuvo un pago foráneo
  de `F` unidades registrado como `L` en moneda principal (tasa `L/F`)
- **WHEN** el cajero agrega una línea de pago `is_foreign_currency` y teclea `F`
- **THEN** el monto en moneda principal de la línea es exactamente `-L`
  (espeja el pago original al centavo, no una reconversión que derive unos
  céntimos), y su `foreign_amount` es `-F`

#### Scenario: Reembolso total que apenas cubre la deuda

- **GIVEN** una orden de reembolso con deuda local `-D` y tasa exacta conocida
- **WHEN** el cajero teclea el monto foráneo que equivale a la deuda (dentro
  de un paso de redondeo foráneo)
- **THEN** el monto en moneda principal se fija exactamente en `-D` (snap),
  sin la deriva sub-céntimo de reconvertir la deuda foránea redondeada

#### Scenario: Sobrepago o pago parcial del reembolso

- **GIVEN** una orden de reembolso con tasa exacta conocida
- **WHEN** el cajero teclea un monto foráneo que excede o es menor que la
  deuda foránea
- **THEN** el monto en moneda principal se calcula como `|foráneo| ×
  tasa_exacta` con signo de reembolso (el excedente queda como vuelto), no
  con la tasa viva ni con la tasa agregada de la orden

#### Scenario: foreign_rate enviado al servidor es positivo y consistente

- **GIVEN** una orden de reembolso con tasa exacta conocida
- **WHEN** se serializa el pago (`serializeForORM`)
- **THEN** `foreign_rate` es `1 / tasa_exacta` (positivo), no un multiplicador
  negativo derivado del descuadre de signo entre el total foráneo (sin signo)
  y `totalDue` (negativo)

#### Scenario: Venta o reembolso sin tender foráneo original no se ve afectado

- **GIVEN** una orden de venta, o un reembolso cuya orden original no tuvo
  pagos con método `is_foreign_currency` (tasa exacta = 0)
- **WHEN** se agrega o edita una línea de pago foránea, o se serializa el pago
- **THEN** todas las conversiones y la `foreign_rate` enviada conservan el
  comportamiento anterior (tasa viva en ventas; proporción por líneas del
  reembolso como respaldo), sin cambios
