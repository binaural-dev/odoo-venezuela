# l10n_ve_account_fiscalyear_closing

## Purpose

Proceso venezolano de cierre de año fiscal montado sobre el asistente genérico `account_fiscal_year_closing`: automatiza la carga de los mapeos de cuentas de resultado, **reemplaza por completo** el cálculo del cierre (no reutiliza `moves_create`) para trabajar con los saldos en moneda alterna (`balance`/`foreign_balance` de `account.move.line`, definidos en `l10n_ve_accountant`) y estampa en cada asiento de cierre la tasa implícita del ejercicio.

Su manifest declara `account_fiscal_year_closing`, `l10n_ve_contact` y `l10n_ve_rate`. Los campos que el código escribe y lee —`foreign_balance`, `foreign_debit`, `foreign_credit`, `foreign_rate`, `foreign_inverse_rate`, `manually_set_rate`— pertenecen a `l10n_ve_accountant`, que **no** figura en `depends` (dependencia implícita: solo `foreign_currency_id` de `res.company` viene de `l10n_ve_rate`).

Extiende también el wizard de descuadre: `foreign_currency_rate` se agrega a `account.fiscalyear.closing.unbalanced.move` y `foreign_debit`/`foreign_credit` a `account.fiscalyear.closing.unbalanced.move.line`; en la práctica ese wizard queda inalcanzable en el flujo venezolano (ver el requirement de cálculo). Expone el flag `l_map` en los formularios de cierre y de plantilla, y sobrescribe `move_line_prepare` (devuelve una tupla de 3 elementos en vez de 2) y `account_lines_get` (devuelve dicts de `read_group` y tiene el filtro por cuenta comentado) de `account.fiscalyear.closing.mapping`, con lo que la ruta heredada `moves_create`/`_mapping_move_lines_get` del módulo base deja de ser utilizable.

## Requirements

### Requirement: Carga automática de mapeos de cuentas de resultado

Al activar el flag `l_map` ("Load Accounts") en una configuración de cierre (`account.fiscalyear.closing.config`, onchange `onchange_l_map`) o en una configuración de plantilla (`account.fiscalyear.closing.config.template`, onchange `inchange_l_map`), el sistema DEBE (MUST) devolver un `{"value": {"mapping_ids": [...]}}` con un mapeo por cada cuenta —buscada con `sudo()` y con `company_ids in [self.env.company.id, False]`, es decir la compañía **activa del usuario**, no la del cierre— cuyo `account_type` sea `income`, `expense`, `income_other`, `expense_depreciation` o `expense_direct_cost` y cuyo `code` no esté vacío. Cada mapeo lleva `name` = nombre de la cuenta y `src_accounts` = código exacto de la cuenta; el destino es la primera cuenta `equity_unaffected` de esa misma compañía (`dest_account_id` en la configuración, el `code` en `dest_account` para la plantilla). Al desactivar el flag, los mapeos se vacían con `[(5, 0, 0)]`. Si no hay ninguna cuenta candidata, el onchange no devuelve nada y `mapping_ids` queda como estaba.

#### Scenario: Activar la carga en una configuración

- **WHEN** un usuario marca `l_map` en una configuración de cierre y existen cuentas de ingreso/gasto con código en su compañía activa
- **THEN** `mapping_ids` se llena con una línea por cuenta, cada una con el código de la cuenta en `src_accounts` y todas apuntando a la primera cuenta `equity_unaffected`

#### Scenario: Desactivar la carga

- **WHEN** un usuario desmarca `l_map`
- **THEN** los mapeos cargados se eliminan de la configuración

#### Scenario: Cierre de una compañía distinta de la activa

- **WHEN** el cierre pertenece a la compañía B pero el usuario tiene como compañía activa la A
- **THEN** los mapeos se cargan con las cuentas y la cuenta destino de la compañía A

### Requirement: Generación del asiento de cierre por cuenta con saldos en ambas monedas

El método `calculate` sobrescrito de `account.fiscalyear.closing` DEBE (MUST) sustituir por completo la generación del módulo base: resuelve una única cuenta destino (la primera `equity_unaffected` con `company_ids in [self.company_id.id, False]`, ignorando el `dest_account_id` de los mapeos), mantiene la verificación previa de borradores cuando `check_draft_moves` está activo, y por cada configuración habilitada agrupa con `read_group` las `account.move.line` de la compañía cuyo asiento no está en `cancel`, con `date` entre `date_start` y `date_end`, sobre las cuentas cuyo `code` está **exactamente** (`in`) en los `src_accounts` de los mapeos, tomando `balance` y `foreign_balance` por cuenta. Por cada cuenta con saldo crea un `account.move` con `ref` = nombre de la configuración, `date` = fecha de la configuración, `fyc_id`, `closing_type` y diario, y dos líneas escritas por el campo `balance`: `-balance` en la cuenta origen y `+balance` con nombre "Result" en la cuenta destino. Se omiten las cuentas con `balance` cero cuando la moneda alterna de la compañía es `base.VEF`, o con `foreign_balance` cero en caso contrario. El método usa `self` (no la variable del bucle) para `_get_balances` y `_create_closing_moves`, por lo que solo admite un cierre a la vez, y devuelve siempre `True`.

#### Scenario: Cuenta de ingreso con saldo en el ejercicio

- **WHEN** se calcula un cierre cuya configuración mapea una cuenta de ingreso con saldo acreedor en el período
- **THEN** se crea un asiento con una línea que revierte ese saldo en la cuenta de ingreso y una línea "Result" por el mismo monto en la primera cuenta de resultados acumulados (`equity_unaffected`), sin importar qué cuenta destino tenga el mapeo

#### Scenario: Cuenta sin saldo foráneo

- **WHEN** la moneda alterna de la compañía no es VEF y una cuenta mapeada tiene `foreign_balance` igual a cero
- **THEN** no se genera asiento de cierre para esa cuenta

#### Scenario: Varios cierres seleccionados

- **WHEN** se ejecuta `calculate` sobre más de un registro de cierre a la vez
- **THEN** la operación falla al evaluar `self.company_id`/`self.id` sobre un recordset múltiple

### Requirement: El flujo venezolano no pasa por moves_create ni por el wizard de descuadre

Como `calculate` construye los asientos directamente con `account.move.create`, el sistema DEBE (MUST) omitir todo el camino del módulo base: no se llama `moves_create`, no se comparan débitos y créditos, no se muestra `account.fiscalyear.closing.unbalanced.move`, no se rellena `move_id` de cada configuración y `calculate` devuelve `True` incluso si no se generó ningún asiento. En consecuencia `button_calculate` siempre pasa el cierre a `calculated`, y el borrado/recálculo posterior opera sobre `move_ids` (que sí queda enlazado por `fyc_id`).

#### Scenario: Configuración sin cuentas con saldo

- **WHEN** se calcula un cierre cuyas cuentas mapeadas no tienen saldo en el período
- **THEN** no se crea ningún asiento pero el cierre queda igualmente en estado `calculated`

#### Scenario: Asiento potencialmente descuadrado

- **WHEN** el cálculo produce un asiento cuyos importes no cuadran
- **THEN** el wizard de asiento descuadrado no se muestra: el asiento se crea (o la creación falla en el propio `account.move`) sin pasar por la comprobación del módulo base

### Requirement: Tasa implícita del asiento de cierre

Cada asiento de cierre generado por `calculate` DEBE (MUST) crearse con `manually_set_rate = True` y con la tasa implícita del saldo de la cuenta: `foreign_rate = |foreign_balance / balance|` cuando la moneda alterna leída de `self.env.company.foreign_currency_id` (la compañía activa del usuario, no la del cierre) es `base.VEF`, o `|balance / foreign_balance|` en caso contrario; `foreign_inverse_rate` es igual a la tasa en el primer caso y su inverso (`1/rate`) en el segundo. Cuando la moneda alterna no es VEF y una cuenta tiene `foreign_balance` distinto de cero con `balance` cero, la tasa resulta 0 y el cálculo de `1/rate` termina en `ZeroDivisionError`.

#### Scenario: Compañía con moneda alterna distinta de VEF

- **WHEN** se genera el asiento de cierre de una cuenta con `balance` 36000 y `foreign_balance` 1000 en una compañía cuya moneda alterna no es VEF
- **THEN** el asiento se crea con `manually_set_rate` activo, `foreign_rate = 36` y `foreign_inverse_rate = 1/36`

#### Scenario: Saldo local cero con saldo foráneo

- **WHEN** la moneda alterna no es VEF y una cuenta mapeada tiene `balance` 0 y `foreign_balance` 500
- **THEN** el cálculo aborta con `ZeroDivisionError` al invertir la tasa

### Requirement: Publicación de los asientos generados por el cierre

El `button_post` sobrescrito DEBE (MUST) publicar (`action_post`) todos los asientos vinculados al cierre (`move_ids`) y después llamar al `button_post` del módulo base, que recorre `move_config_ids` posteando su `move_id` —vacío en este flujo— y escribe el estado `posted`.

#### Scenario: Publicar el cierre venezolano

- **WHEN** se pulsa el botón de publicar sobre un cierre calculado con asientos en `move_ids`
- **THEN** esos asientos se postean, el recorrido de configuraciones del módulo base no publica nada adicional y el cierre queda en estado `posted`

### Requirement: Compañía por defecto en cierres y plantillas

El modelo abstracto `account.fiscalyear.closing.abstract` DEBE (MUST) redefinir `company_id` como Many2one a `res.company` con la compañía activa del usuario (`self.env.company.id`) por defecto, aplicándose tanto a los cierres como a las plantillas que heredan de él.

#### Scenario: Crear un cierre nuevo

- **WHEN** un usuario crea un registro de cierre fiscal sin indicar compañía
- **THEN** `company_id` queda establecido a la compañía activa del usuario
