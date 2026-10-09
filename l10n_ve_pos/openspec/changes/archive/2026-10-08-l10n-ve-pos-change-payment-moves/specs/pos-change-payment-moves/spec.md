# Spec delta: pos-change-payment-moves

## ADDED Requirements

### Requirement: El vuelto va en el asiento de pago de su método

Al crear los asientos de pago de una orden facturada, el sistema SHALL fundir el
vuelto en efectivo solo con un cobro en efectivo del mismo método de pago. Si la
orden no tiene un cobro en efectivo de ese método, si el método concilia por
pago (`split_transactions`) o si el vuelto está en varios métodos, cada vuelto
SHALL llevar su propio asiento de pago. Un asiento de pago MUST NOT reunir pagos
de métodos distintos.

#### Scenario: Vuelto en un efectivo distinto al del cobro

- **GIVEN** una venta de 54.627,12 Bs cobrada con 70 $ en Efectivo USD y un
  vuelto de 1.606,68 en Efectivo Bs
- **WHEN** se crean sus asientos de pago
- **THEN** hay dos asientos, uno por pago, y al cerrar la sesión la cuenta por
  cobrar del PdV queda conciliada

#### Scenario: Vuelto en el mismo efectivo del cobro

- **GIVEN** un cobro de 30.000 en Efectivo Bs y un vuelto de 3.320,79 en
  Efectivo Bs
- **WHEN** se crean sus asientos de pago
- **THEN** hay un solo asiento de 26.679,21 con los dos pagos

#### Scenario: Vuelto en un método dividido

- **GIVEN** un cobro y su vuelto en un efectivo con `split_transactions`
- **WHEN** se crean sus asientos de pago
- **THEN** hay dos asientos, uno por pago

#### Scenario: Vuelto en varios métodos

- **GIVEN** un cobro en Efectivo USD, un vuelto en Efectivo USD y otro en
  Efectivo Bs
- **WHEN** se crean sus asientos de pago
- **THEN** hay tres asientos, uno por pago

#### Scenario: Factura de una orden con el vuelto en su propio asiento

- **GIVEN** una factura de 116 cobrada con 120 en un efectivo y un vuelto de 4
  en otro
- **WHEN** se crean los asientos de pago y se concilian con la factura
- **THEN** la factura queda pagada

#### Scenario: Dos cobros en efectivo y vuelto en uno de sus métodos

- **GIVEN** un cobro en Efectivo USD, otro en Efectivo Bs y el vuelto en
  Efectivo Bs
- **WHEN** se crean sus asientos de pago
- **THEN** el vuelto va en el asiento del cobro en Efectivo Bs, aunque el core
  hubiera tomado primero el de Efectivo USD

### Requirement: Cada asiento de pago lleva la tasa y el alterno de sus pagos

El sistema SHALL identificar los pagos de cada asiento de pago por su relación
(`pos_payment_ids`), no por el monto. El asiento SHALL llevar la tasa del cobro
y, en alterno, la suma con signo de los montos foráneos de sus pagos.

#### Scenario: Asiento con el cobro y su vuelto

- **GIVEN** un cobro con 74,68 de alterno y su vuelto con −6,68
- **WHEN** se crea su asiento de pago
- **THEN** el asiento lleva la tasa del cobro fijada y 68,00 de alterno en cada
  línea

#### Scenario: Dos pagos del mismo monto

- **GIVEN** dos pagos de 58,00 con alternos distintos
- **WHEN** se crean sus asientos de pago
- **THEN** cada asiento lleva el alterno de su propio pago
