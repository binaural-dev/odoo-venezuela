## ADDED Requirements

### Requirement: El cross move se fecha en el día del usuario

`_create_cross_move` DEBE (MUST) fechar el asiento en el día del usuario (`fields.Date.context_today`) cuando recibe un Datetime en UTC (`stop_at` de la sesión o `create_date` del pago), y no truncarlo al día UTC. Desde las 8 pm de Caracas el día UTC ya es el siguiente, todavía sin tasa, y `l10n_ve_accountant` detenía el cierre de la sesión.

#### Scenario: Cierre a las 8:30 pm de Caracas con un método que no identifica cliente

- **WHEN** la sesión se cierra con `stop_at` a las 00:30 UTC del día siguiente y solo hay tasa del día del usuario
- **THEN** el cross move del método se crea con la fecha del día del usuario, sin pedir la tasa del día UTC

#### Scenario: Pago registrado a las 8:30 pm de Caracas con un método que identifica cliente

- **WHEN** el pago se registró a las 00:30 UTC del día siguiente y solo hay tasa del día del usuario
- **THEN** el cross move de ese pago se crea con la fecha del día del usuario
