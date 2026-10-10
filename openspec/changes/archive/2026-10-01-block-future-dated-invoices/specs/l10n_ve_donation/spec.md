## ADDED Requirements

### Requirement: La nota de crédito de reverso de una donación usa la fecha del usuario

La nota de crédito de reverso de una donación DEBE (MUST) crearse con la fecha `fields.Date.context_today(self)` (zona horaria del usuario) y no con la fecha UTC del servidor (`fields.Date.today()`), tanto en el wizard de reversión de `action_post` como en el valor por defecto de `_reverse_moves`, para no quedar con fecha posterior a "hoy" y ser rechazada por el guard de fecha futura de `l10n_ve_invoice` al confirmarse.

#### Scenario: Donación confirmada en la noche (hora de Caracas)

- **WHEN** se confirma una factura de donación entre las 20:00 y las 24:00 hora de Caracas, cuando la fecha UTC ya es la del día siguiente
- **THEN** la nota de crédito de reverso se crea con la fecha local de hoy y se confirma sin error
