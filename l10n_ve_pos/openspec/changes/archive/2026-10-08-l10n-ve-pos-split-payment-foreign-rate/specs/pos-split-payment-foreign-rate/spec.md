# Spec delta: pos-split-payment-foreign-rate

## ADDED Requirements

### Requirement: El pago split de banco cuadra en alterno con la tasa de la caja

Al cerrar una sesión, el sistema SHALL crear el `account.payment` de cada cobro
de un método de banco con `split_transactions` con la tasa con la que cobró la
caja (`pos.payment.foreign_rate`) y SHALL poner en todas las líneas de su
asiento el monto alterno cobrado (`foreign_amount`). El asiento MUST cuadrar en
alterno aunque la tasa de la fecha del cierre sea otra.

#### Scenario: Banco en Bs con la tasa cambiada antes del cierre

- **GIVEN** un cobro de 10.000 Bs por un banco sin moneda propia con
  `split_transactions`, a 803,34 (12,45 $)
- **AND** la tasa del día del cierre en 850
- **WHEN** se cierra la sesión
- **THEN** la línea de liquidez y la de la cuenta del cliente llevan 12,45 $ de
  alterno
- **AND** el pago lleva la tasa 803,34

#### Scenario: Reembolso por el mismo banco

- **GIVEN** un pago saliente por un banco sin moneda propia con
  `split_transactions` y la tasa cambiada
- **WHEN** se cierra la sesión
- **THEN** el asiento del pago cuadra en alterno con el monto alterno del cobro
