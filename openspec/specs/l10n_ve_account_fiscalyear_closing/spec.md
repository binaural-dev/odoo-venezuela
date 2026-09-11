# l10n_ve_account_fiscalyear_closing

## Purpose

Proceso venezolano de cierre de año fiscal montado sobre el asistente genérico `account_fiscal_year_closing`: automatiza la carga de los mapeos de cuentas de resultado y **reemplaza por completo** el cálculo del cierre (no reutiliza `moves_create`) para trabajar directamente con los saldos en moneda alterna (`balance`/`foreign_balance` de `account.move.line`, provistos por `l10n_ve_accountant`) extraídos de los asientos de origen, sin derivar ninguna tasa sintética.

Su manifest declara `account_fiscal_year_closing`, `l10n_ve_accountant`, `l10n_ve_contact` y `l10n_ve_rate` como dependencias. Los campos `foreign_balance`, `foreign_debit`, `foreign_credit`, `foreign_rate`, `foreign_inverse_rate` que usa el código pertenecen a `l10n_ve_accountant`, ahora declarado explícitamente en `depends`; `foreign_currency_id` de `res.company` viene de `l10n_ve_rate`.

Expone el flag `l_map` en los formularios de cierre y de plantilla para autocompletar los mapeos de cuentas de resultado, y sobrescribe `move_line_prepare` (devuelve una tupla de 3 elementos: `balance`, `move_line`, `rate`) y `account_lines_get` (usa `read_group` agrupando por cuenta) de `account.fiscalyear.closing.mapping`. La generación real de los asientos de cierre, sin embargo, no pasa por `moves_create`/`_mapping_move_lines_get` del módulo base ni por su wizard de descuadre: `calculate()` se redefine íntegramente en este módulo (ver requirement correspondiente).

## Requirements

### Requirement: Carga automática de mapeos de cuentas de resultado

Al activar el flag `l_map` ("Load Accounts") en una configuración de cierre (`account.fiscalyear.closing.config`, onchange `onchange_l_map`) o en una configuración de plantilla (`account.fiscalyear.closing.config.template`, onchange `inchange_l_map`), el sistema DEBE (MUST) devolver un `{"value": {"mapping_ids": [...]}}` con un mapeo por cada cuenta —buscada con `company_ids in [self.env.company.id, False]`, es decir la compañía **activa del usuario**, no necesariamente la del cierre— cuyo `account_type` sea `income`, `expense`, `income_other`, `expense_depreciation` o `expense_direct_cost` y cuyo `code` no esté vacío. Cada mapeo lleva `name` = nombre de la cuenta y `src_accounts` = código exacto de la cuenta; el destino es la primera cuenta `equity_unaffected` de esa misma compañía (`dest_account_id` en la configuración, el `code` en `dest_account` para la plantilla). Al desactivar el flag, los mapeos se vacían con `[(5, 0, 0)]`. Si no hay ninguna cuenta candidata, el onchange no devuelve nada y `mapping_ids` queda como estaba. Ninguno de los dos onchanges usa `sudo()`: el usuario que edita la configuración debe tener por sí mismo permiso de lectura sobre el plan de cuentas de su compañía activa.

#### Scenario: Activar la carga en una configuración

- **WHEN** un usuario marca `l_map` en una configuración de cierre y existen cuentas de ingreso/gasto con código en su compañía activa
- **THEN** `mapping_ids` se llena con una línea por cuenta, cada una con el código de la cuenta en `src_accounts` y todas apuntando a la primera cuenta `equity_unaffected`

#### Scenario: Desactivar la carga

- **WHEN** un usuario desmarca `l_map`
- **THEN** los mapeos cargados se eliminan de la configuración

#### Scenario: Cierre de una compañía distinta de la activa

- **WHEN** el cierre pertenece a la compañía B pero el usuario tiene como compañía activa la A
- **THEN** los mapeos se cargan con las cuentas y la cuenta destino de la compañía A, no de la B

### Requirement: Validación previa a calcular: cuenta de resultados, borradores y fecha de bloqueo

El método `calculate` sobrescrito de `account.fiscalyear.closing` DEBE (MUST), antes de generar ningún asiento: invocar `_check_fiscal_lock_date` (heredado tal cual del módulo base, invocado explícitamente porque este `calculate` no llama a `super()`), y por cada `closing` del recordset, resolver una cuenta de destino `equity_unaffected` (`company_ids in [closing.company_id.id, False]`, usando **la compañía del cierre que se está procesando**, no `self.company_id` ni `self.env.company`) lanzando `UserError` si no existe ninguna, y ejecutar `draft_moves_check` cuando `check_draft_moves` esté activo. Todo el flujo multi-registro (varios cierres a la vez, incluso de compañías distintas) usa consistentemente `closing.company_id` dentro del bucle en lugar de una variable de compañía calculada una sola vez fuera de él.

#### Scenario: Compañía sin cuenta de resultados acumulados configurada

- **WHEN** se calcula un cierre cuya compañía no tiene ninguna cuenta de tipo `equity_unaffected`
- **THEN** se lanza `UserError` indicando que debe configurarse esa cuenta antes de cerrar

#### Scenario: Varios cierres de compañías distintas en el mismo recordset

- **WHEN** se ejecuta `calculate` sobre cierres de dos compañías distintas a la vez
- **THEN** cada cierre resuelve su propia cuenta `equity_unaffected` y aplica sus propias validaciones usando su `company_id`, sin mezclar datos entre compañías

#### Scenario: Existen borradores en el período

- **WHEN** `check_draft_moves` está activo y hay asientos en borrador dentro del período del cierre
- **THEN** se lanza `ValidationError` y no se genera ningún asiento

### Requirement: Generación del asiento de cierre por cuenta con saldos en ambas monedas

Por cada configuración habilitada, `calculate` DEBE (MUST) agrupar con `read_group` (vía `_get_balances`) las `account.move.line` de la compañía del cierre cuyo asiento no está en `cancel`, con `date` entre `date_start` y `date_end`, sobre las cuentas cuyo `code` está exactamente (`in`, comparación exacta, no `=ilike`) entre los `src_accounts` de los mapeos de la configuración, obteniendo `balance` y `foreign_balance` agregados por cuenta. Por cada cuenta con saldo, `_create_closing_moves` crea un `account.move` con `ref` = nombre de la configuración, `date` = fecha de la configuración, `fyc_id`, `closing_type` = `move_type` y diario de la configuración, con dos líneas: una que revierte el saldo (`-balance`/`-foreign_balance`) en la cuenta origen con `not_foreign_recalculate = True`, y otra con nombre "Result" que asienta el saldo positivo (`+balance`/`+foreign_balance`, también con `not_foreign_recalculate = True`) en la cuenta destino `equity_unaffected` resuelta para esa compañía —la única cuenta destino usada, sin importar qué `dest_account_id` tenga cada mapeo—. Cuando la compañía no tiene `foreign_currency_id` configurada, o esta coincide con `base.VEF` (caso "moneda única"), la cuenta se omite si su `balance` es cero; en cualquier otro caso (bimoneda real) se omite si su `foreign_balance` es cero.

#### Scenario: Cuenta de ingreso con saldo en el ejercicio

- **WHEN** se calcula un cierre cuya configuración mapea una cuenta de ingreso con saldo acreedor en el período
- **THEN** se crea un asiento con una línea que revierte ese saldo en la cuenta de ingreso y una línea "Result" por el mismo monto en la cuenta de resultados acumulados (`equity_unaffected`) de la compañía del cierre, sin importar qué cuenta destino tenga el mapeo

#### Scenario: Compañía sin moneda alterna configurada (single_currency)

- **WHEN** la compañía del cierre no tiene `foreign_currency_id` configurada
- **THEN** el criterio para generar o no el asiento se basa únicamente en `balance` (moneda local), ignorando `foreign_balance`

#### Scenario: Cuenta sin saldo foráneo en compañía bimoneda

- **WHEN** la moneda alterna de la compañía no es `base.VEF` y una cuenta mapeada tiene `foreign_balance` igual a cero
- **THEN** no se genera asiento de cierre para esa cuenta, aunque tenga `balance` distinto de cero

### Requirement: Sin tasa sintética derivada de los totales

Los asientos de cierre generados por `_create_closing_moves` DEBEN (MUST) construirse sin fijar `manually_set_rate`, `foreign_rate` ni `foreign_inverse_rate` en el asiento: los importes en moneda alterna (`foreign_balance`) se pasan directamente, línea por línea, desde el valor ya agregado por `read_group` sobre `account.move.line.foreign_balance`, sin derivar ninguna tasa matemáticamente a partir de la relación entre `balance` y `foreign_balance` del asiento resultante. Esto evita la división por cero que antes ocurría cuando `balance` era 0 con `foreign_balance` distinto de cero.

#### Scenario: Cuenta con balance local cero y saldo foráneo distinto de cero

- **WHEN** una cuenta mapeada tiene `balance` 0 y `foreign_balance` 500 en el período, en una compañía bimoneda
- **THEN** el asiento (si se genera, según el criterio de single_currency que aplique) no requiere calcular ninguna tasa y no se produce ningún error de división por cero

### Requirement: El flujo venezolano no pasa por moves_create ni por el wizard de descuadre

Como `calculate` construye los asientos directamente con `account.move.create`, el sistema DEBE (MUST) omitir todo el camino del módulo base: no se llama `moves_create`, no se comparan débitos y créditos del asiento resultante, no se muestra `account.fiscalyear.closing.unbalanced.move`, no se rellena `move_id` de cada configuración y `calculate` devuelve `True` incluso si no se generó ningún asiento. En consecuencia `button_calculate` siempre pasa el cierre a `calculated` cuando `calculate` no lanza excepción, y el borrado/recálculo posterior (heredado del módulo base) opera sobre `move_ids` (que sí queda enlazado por `fyc_id`), no sobre `move_config_ids.move_id`.

#### Scenario: Configuración sin cuentas con saldo

- **WHEN** se calcula un cierre cuyas cuentas mapeadas no tienen saldo en el período
- **THEN** no se crea ningún asiento pero el cierre queda igualmente en estado `calculated`

### Requirement: Publicación de los asientos generados por el cierre

El `button_post` sobrescrito DEBE (MUST) publicar (`action_post`) todos los asientos vinculados al cierre (`move_ids`) y después llamar al `button_post` del módulo base, que recorre `move_config_ids` posteando su `move_id` —vacío en este flujo, por lo que no publica nada adicional— y escribe el estado `posted`.

#### Scenario: Publicar el cierre venezolano

- **WHEN** se pulsa el botón de publicar sobre un cierre calculado con asientos en `move_ids`
- **THEN** esos asientos se postean, el recorrido de configuraciones del módulo base no publica nada adicional y el cierre queda en estado `posted`

### Requirement: Compañía por defecto en cierres y plantillas

El modelo abstracto `account.fiscalyear.closing.abstract` DEBE (MUST) redefinir `company_id` como Many2one a `res.company` con la compañía activa del usuario (`self.env.company.id`) por defecto, aplicándose tanto a los cierres como a las plantillas que heredan de él.

#### Scenario: Crear un cierre nuevo

- **WHEN** un usuario crea un registro de cierre fiscal sin indicar compañía
- **THEN** `company_id` queda establecido a la compañía activa del usuario

### Requirement: `move_line_prepare` extendido devuelve una tasa con signo comparado, no en valor absoluto

`account.fiscalyear.closing.mapping.move_line_prepare` DEBE (MUST) sobrescribir la versión del módulo base para devolver una tupla de 3 elementos `(balance, move_line, abs(rate))` en vez de `(balance, move_line)`. `rate` se calcula como `foreign_balance / balance` cuando `balance > foreign_balance` (comparación numérica con signo, **no** en valor absoluto), y como `balance / foreign_balance` en caso contrario; el valor final que se retorna es `abs(rate)`, pero el `else` que decide qué división ejecutar no aplica `abs()` a ninguno de los dos operandos antes de comparar. Este método solo lo invoca código que llama directamente a `move_line_prepare` (por ejemplo pruebas): el flujo estándar de `calculate()` de este módulo no pasa por `moves_create`/`move_line_prepare`, así que este valor de `rate` no participa en la generación real de los asientos de cierre.

Por la comparación con signo (no absoluta), si `foreign_balance` es `0` y `balance` es negativo, `balance > foreign_balance` es falso (un negativo nunca es mayor que 0), así que se ejecuta la rama `balance / foreign_balance` y el método termina en `ZeroDivisionError`.

#### Scenario: Invocación directa de move_line_prepare con montos iguales

- **WHEN** se llama directamente `move_line_prepare` sobre un mapeo con líneas cuyo balance y saldo foráneo son iguales y positivos (mismo importe en ambas monedas)
- **THEN** devuelve una tupla de 3 elementos con `rate` igual a `1.0`

#### Scenario: Saldo local negativo sin saldo foráneo

- **WHEN** se llama `move_line_prepare` sobre líneas con `balance` negativo y `foreign_balance` igual a `0`
- **THEN** el método termina en `ZeroDivisionError` en vez de devolver una tasa, porque la comparación `balance > foreign_balance` (con signo) elige dividir entre `foreign_balance`

### Requirement: `moves_create`/`_mapping_move_lines_get` del módulo base quedan inutilizables con este módulo instalado

Como `l10n_ve_account_fiscalyear_closing` sobrescribe `_mapping_move_lines_get(self, src, account_map)` en `account.fiscalyear.closing.config` con una firma que exige dos argumentos posicionales adicionales, mientras que el módulo base la define como `_mapping_move_lines_get(self)` (sin argumentos) y la invoca así desde `moves_create()`, el sistema DEBE (MUST) fallar con `TypeError` si algún código (propio o de un módulo dependiente) llama a `moves_create()` sobre una configuración con este módulo instalado. No es una ruta "no usada": es una ruta rota por incompatibilidad de firma. El flujo real de cierre en este módulo nunca pasa por ahí porque `calculate()` está completamente reemplazado y no llama a `moves_create()`.

#### Scenario: Llamar moves_create con l10n_ve instalado

- **WHEN** código externo invoca `config.moves_create()` sobre una `account.fiscalyear.closing.config` con `l10n_ve_account_fiscalyear_closing` instalado
- **THEN** la llamada interna a `self._mapping_move_lines_get()` (sin argumentos) falla con `TypeError` por los dos argumentos posicionales faltantes
