## MODIFIED Requirements

### Requirement: Cuenta IGTF exigida solo cuando IGTF se aplica

Al abrir una sesión de PoS (`action_pos_session_open`), el módulo SHALL exigir
`company_id.customer_account_igtf_id` **únicamente** cuando IGTF se aplica en esa
caja — esto es, cuando algún método de pago del `config_id` tiene
`apply_igtf=True`. Si ningún método aplica IGTF, la apertura de sesión NO debe
bloquearse por falta de la cuenta IGTF.

#### Scenario: Caja sin IGTF

- **WHEN** se abre una sesión cuyo `config_id` no tiene ningún método de pago
  con `apply_igtf=True`
- **THEN** la sesión abre normalmente (`super().action_pos_session_open()`), sin
  exigir `customer_account_igtf_id`

#### Scenario: Caja con IGTF sin cuenta configurada

- **WHEN** se abre una sesión cuyo `config_id` tiene al menos un método de pago
  con `apply_igtf=True` y la compañía no tiene `customer_account_igtf_id`
- **THEN** se lanza `ValidationError` pidiendo configurar la cuenta y el
  porcentaje IGTF

#### Scenario: Caja con IGTF y cuenta configurada

- **WHEN** se abre una sesión con IGTF en uso y `customer_account_igtf_id`
  configurada
- **THEN** la sesión abre normalmente
