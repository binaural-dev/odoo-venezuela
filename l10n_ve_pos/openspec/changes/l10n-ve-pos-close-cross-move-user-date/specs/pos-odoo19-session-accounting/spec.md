# Spec delta: pos-odoo19-session-accounting

## ADDED Requirements

### Requirement: El asiento de cruce del cierre DEBE fecharse con el día del usuario

`_validate_cross_move` SHALL fechar cada asiento de cruce con la fecha del usuario
(`fields.Date.context_today`) de `pos.session.stop_at` (o del ahora, si no hay) en
el método combinado, y de `pos.payment.create_date` en el método con
`split_transactions`. No SHALL usar la fecha UTC de esos Datetime.

#### Scenario: Cierre a las 8 pm de Caracas sin la tasa de mañana

- **GIVEN** son las 20:30 en Caracas (00:30 UTC del día siguiente) y solo existe la
  tasa del día del usuario
- **WHEN** se crean los asientos de cruce del cierre
- **THEN** cada asiento lleva la fecha del día del usuario y no se lanza el error de
  tasa inexistente

#### Scenario: Método con split_transactions

- **GIVEN** un método con `split_transactions` cuyo pago se creó a las 20:30 de Caracas
- **WHEN** se crea su asiento de cruce
- **THEN** el asiento lleva el día del usuario de `payment.create_date`

### Requirement: Las conversiones del cierre con un Datetime DEBEN usar el día del usuario

`pos.session._amount_converter` y `_prepare_statement_line_amount_values` SHALL
convertir con la tasa del día del usuario (`fields.Date.context_today`) cuando la fecha
es un Datetime (`stop_at`, `payment.payment_date`, `date_order`). Una fecha (no
Datetime) SHALL usarse tal cual.

#### Scenario: Cierre a las 8 pm de Caracas con la tasa de mañana ya publicada

- **GIVEN** son las 20:30 en Caracas (00:30 UTC del día siguiente) y existen las tasas del día del usuario (40) y del día siguiente (50)
- **WHEN** se convierte un monto de la sesión con `stop_at` o `payment.payment_date`
- **THEN** se usa la tasa del día del usuario, no la del día siguiente

#### Scenario: Fecha sin hora

- **WHEN** quien llama pasa una fecha (no Datetime)
- **THEN** se convierte con la tasa de esa fecha, sin cambios
