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
