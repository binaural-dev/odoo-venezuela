# l10n_ve_account_fiscalyear_closing

## Purpose

Proceso venezolano de cierre de año fiscal montado sobre el asistente genérico `account_fiscal_year_closing`: automatiza la carga de los mapeos de cuentas de resultado, reescribe el cálculo del cierre para trabajar con los saldos en moneda alterna (`foreign_debit`/`foreign_credit` de `l10n_ve_accountant`) y estampa en cada asiento de cierre la tasa implícita del ejercicio. Depende de `account_fiscal_year_closing`, `l10n_ve_contact` y `l10n_ve_rate`. Extiende también el wizard `account.fiscalyear.closing.unbalanced.move` agregando los campos `foreign_currency_rate`, `foreign_debit` y `foreign_credit` a sus líneas, y expone el flag `l_map` en los formularios de cierre y de plantilla.

## Requirements

### Requirement: Carga automática de mapeos de cuentas de resultado

Al activar el flag `l_map` ("Load Accounts") en una configuración de cierre (`account.fiscalyear.closing.config`) o en una configuración de plantilla (`account.fiscalyear.closing.config.template`), el onchange DEBE (MUST) poblar `mapping_ids` con un mapeo por cada cuenta de la compañía cuyo `account_type` sea `income`, `expense`, `income_other`, `expense_depreciation` o `expense_direct_cost`, usando como destino la primera cuenta de tipo `equity_unaffected` (en la config el `dest_account_id`, en la plantilla el código `dest_account`); al desactivarlo, los mapeos se vacían.

#### Scenario: Activar la carga en una configuración

- **WHEN** un usuario marca `l_map` en una configuración de cierre
- **THEN** `mapping_ids` se llena con una línea por cuenta de ingreso/gasto, todas apuntando a la primera cuenta `equity_unaffected` de la compañía

#### Scenario: Desactivar la carga

- **WHEN** un usuario desmarca `l_map`
- **THEN** los mapeos cargados se eliminan de la configuración

### Requirement: Generación del asiento de cierre por cuenta con saldos en ambas monedas

El método `calculate` sobrescrito de `account.fiscalyear.closing` DEBE (MUST), por cada configuración habilitada, agrupar (`read_group`) las líneas contables no canceladas del período por cuenta —tomando `balance` y `foreign_balance`— para las cuentas cuyo código coincide exactamente con los `src_accounts` de los mapeos, y crear un asiento por cada cuenta con saldo: una línea que revierte el `balance` en la cuenta origen y una línea "Result" con el `balance` en la primera cuenta `equity_unaffected` de la compañía. Se omiten las cuentas con `balance` cero cuando la moneda alterna de la compañía es `base.VEF`, o con `foreign_balance` cero en caso contrario. La verificación previa de borradores (`draft_moves_check` de `account_fiscal_year_closing`) se mantiene.

#### Scenario: Cuenta de ingreso con saldo en el ejercicio

- **WHEN** se calcula un cierre cuya configuración mapea una cuenta de ingreso con saldo acreedor en el período
- **THEN** se crea un asiento con una línea que revierte ese saldo en la cuenta de ingreso y una línea "Result" por el mismo monto en la cuenta de resultados acumulados (`equity_unaffected`)

#### Scenario: Cuenta sin saldo foráneo

- **WHEN** la moneda alterna de la compañía no es VEF y una cuenta mapeada tiene `foreign_balance` igual a cero
- **THEN** no se genera asiento de cierre para esa cuenta

### Requirement: Tasa implícita del asiento de cierre

Cada asiento de cierre generado por `calculate` DEBE (MUST) crearse con `manually_set_rate = True` y con la tasa implícita del saldo de la cuenta: `foreign_rate = |foreign_balance / balance|` cuando la moneda alterna de la compañía (`foreign_currency_id` de `l10n_ve_rate`) es `base.VEF`, o `|balance / foreign_balance|` en caso contrario; `foreign_inverse_rate` es igual a la tasa en el primer caso y su inverso (`1/rate`) en el segundo.

#### Scenario: Compañía con moneda alterna distinta de VEF

- **WHEN** se genera el asiento de cierre de una cuenta con `balance` 36000 y `foreign_balance` 1000 en una compañía cuya moneda alterna no es VEF
- **THEN** el asiento se crea con `manually_set_rate` activo, `foreign_rate = 36` y `foreign_inverse_rate = 1/36`

### Requirement: Publicación de los asientos generados por el cierre

El `button_post` sobrescrito DEBE (MUST) publicar (`action_post`) todos los asientos vinculados al cierre (`move_ids`) antes de ejecutar la publicación estándar de `account_fiscal_year_closing`.

#### Scenario: Publicar el cierre venezolano

- **WHEN** se pulsa el botón de publicar sobre un cierre calculado con asientos en `move_ids`
- **THEN** esos asientos se postean y el cierre queda en estado `posted`

### Requirement: Compañía por defecto en cierres y plantillas

El modelo abstracto `account.fiscalyear.closing.abstract` DEBE (MUST) tener como valor por defecto de `company_id` la compañía activa del usuario (`self.env.company`), aplicándose tanto a los cierres como a las plantillas que heredan de él.

#### Scenario: Crear un cierre nuevo

- **WHEN** un usuario crea un registro de cierre fiscal sin indicar compañía
- **THEN** `company_id` queda establecido a la compañía activa del usuario
