## Why

`action_pos_session_open` (override en `l10n_ve_pos_igtf/models/pos_session.py`)
exigía `company_id.customer_account_igtf_id` **en toda apertura de sesión**, sin
verificar si IGTF realmente se usa en esa caja. El mensaje dice "You have the
IGTF configuration turned on…", pero el código nunca chequeaba ese "turned on".

Consecuencias:
- **Bug latente de producción**: una empresa con el módulo instalado pero que
  NO usa IGTF no puede abrir caja hasta configurar la cuenta IGTF.
- **CI rojo**: al ejecutarse los tests de `l10n_ve_pos`, `l10n_ve_pos_igtf` y
  `l10n_ve_pos_mf` en la misma base (el PR de la salida 2Doce toca los tres),
  cada `pos.session` creada en los tests de `l10n_ve_pos` disparaba esta
  validación → 37 errores de los 34 reportados (setUpClass en cascada). Los
  archivos afectados son idénticos a 19.0: fallo preexistente que el scope del
  CI destapó, no una regresión del feature.

Además, `l10n_ve_pos_igtf/tests/test_pos_igtf_migration.py` buscaba
`account.account` por `company_id`, campo eliminado en Odoo 19 (ahora
`company_ids`, Many2many) → 1 error de setUpClass.

## What Changes

- `models/pos_session.py`: `action_pos_session_open` solo exige
  `customer_account_igtf_id` cuando IGTF se aplica de verdad — es decir, cuando
  algún método de pago del `config_id` tiene `apply_igtf=True`
  (`igtf_in_use = any(config_id.payment_method_ids.mapped("apply_igtf"))`).
- `tests/test_pos_igtf_migration.py`: el search de `account.account` usa
  `("company_ids", "in", cls.company.id)` (Odoo 19) en vez de
  `("company_id", "=", …)`.
- Bump de versión del manifest (`1.3` → `1.4`).

## Capabilities

### Modified Capabilities

- `backend-order-validation`: la validación de cuenta IGTF al abrir sesión pasa
  a ser condicional a que IGTF esté en uso en la caja.

## Impact

- Módulo: `l10n_ve_pos_igtf` (`models/pos_session.py`,
  `tests/test_pos_igtf_migration.py`, manifest).
- Desbloquea el CI del PR #1252 (salida 2Doce) y corrige un bug latente:
  empresas sin IGTF ya pueden abrir caja con el módulo instalado.
- Cambio de comportamiento en producción: quien SÍ usa IGTF (método de pago con
  `apply_igtf`) sigue obligado a configurar `customer_account_igtf_id`.
