# account_fiscal_year_closing

## Purpose

Asistente genérico de cierre de año fiscal (origen OCA account-closing, Tecnativa). Define los modelos concretos `account.fiscalyear.closing` (el cierre de un ejercicio), `account.fiscalyear.closing.config` (cada asiento a generar), `account.fiscalyear.closing.mapping` (mapeo de cuentas origen → destino), `account.fiscalyear.closing.type` (tipo de cierre por tipo de cuenta) y sus contrapartes plantilla (`account.fiscalyear.closing.template`, `...config.template`, `...mapping.template`, `...type.template`). Depende únicamente de `account`. Los modelos concretos heredan de los abstractos `account.fiscalyear.closing.abstract`, `account.fiscalyear.closing.config.abstract`, `account.fiscalyear.closing.mapping.abstract` y `account.fiscalyear.closing.type.abstract` (definidos en `models/account_fiscalyear_closing_abstract.py`); el wizard `account.fiscalyear.closing.unbalanced.move` se define en `wizards/` y se invoca desde `calculate()`. La extensión venezolana del proceso vive en `l10n_ve_account_fiscalyear_closing`.

Estado actual (post-corrección): el módulo es instalable, con `security/ir.model.access.csv` y `security/account_fiscalyear_closing_security.xml` presentes, y `wizards/account_fiscal_year_closing_unbalanced_move_views.xml` sí existe en el árbol. Los campos `fyc_id` y `closing_type` de `account.move` se definen en `models/account_move.py`. El antiguo constraint SQL `unique(year, company_id)` fue reemplazado por el constraint Python `_check_period_overlap`, que permite varios cierres por compañía/año siempre que sus rangos de fechas no se solapen. `_moves_remove` ya nunca elimina un asiento que llegó a postearse: lo cancela (`button_cancel()` de `account.move`, que desconcilia, pasa a borrador y cancela). `account.fiscalyear.closing.mapping.create`/`write` normalizan correctamente `dest_account_id` acepte el valor un id entero, una lista/tupla o un recordset. `template_id` en `account.fiscalyear.closing.config.template` ya no es `required=True`, para permitir crear/editar plantillas de configuración de forma independiente antes de asociarlas a una plantilla padre.

## Requirements

### Requirement: Flujo de estados del cierre

El registro de cierre (`account.fiscalyear.closing`) DEBE (MUST) manejar los estados `draft`, `calculated` (etiqueta "Processed"), `posted` y `cancelled`: `button_calculate` pasa a `calculated` y estampa `calculation_date` solo si el cálculo devolvió `True`; `button_cancel` invoca `_moves_remove` (cancela, no elimina, los asientos posteados) y pasa a `cancelled`; `button_recover` escribe `draft` y limpia `calculation_date`. Los métodos no validan el estado de origen: es la vista formulario la que expone `button_calculate` solo en `draft`, `button_recalculate` y `button_post` solo en `calculated`, `button_cancel` en `calculated` o `posted`, y `button_recover` únicamente en `cancelled`.

#### Scenario: Cálculo exitoso

- **WHEN** se pulsa `button_calculate` y `calculate` devuelve `True` (todos los asientos configurados se generaron balanceados)
- **THEN** el cierre queda en estado `calculated` con `calculation_date` en la fecha/hora actual

#### Scenario: Recuperación a borrador

- **WHEN** se pulsa `button_recover` sobre un cierre cancelado (único estado donde el botón es visible)
- **THEN** el cierre vuelve a estado `draft` y `calculation_date` queda vacío

### Requirement: Verificación de asientos en borrador antes de calcular

Cuando el flag `check_draft_moves` está activo, el método `calculate` DEBE (MUST) ejecutar `draft_moves_check` antes de generar ningún asiento; este método lanza `ValidationError` listando ID, fecha, número y referencia de cada `account.move` en estado `draft` de la compañía cuyo `date` cae dentro de `date_start`–`date_end`.

#### Scenario: Existen borradores en el período

- **WHEN** se calcula un cierre con `check_draft_moves` activo y hay al menos un asiento en borrador dentro del período
- **THEN** se lanza un error de validación que enumera los asientos en borrador y no se genera ningún asiento de cierre

### Requirement: Validación de la fecha de bloqueo contable antes de calcular

`calculate` DEBE (MUST) invocar `_check_fiscal_lock_date` antes de crear ningún asiento: por cada configuración habilitada con diario y fecha definidos, obtiene la fecha de bloqueo efectiva para ese diario (`company_id._get_user_fiscal_lock_date(journal)`, que combina la fecha de bloqueo genérica con la específica por tipo de diario — `sale_lock_date`, `purchase_lock_date`, etc.) y lanza `ValidationError` si la fecha de la configuración es menor o igual a esa fecha de bloqueo. Esto evita que Odoo mueva silenciosamente la fecha del asiento a `lock_date + 1 día`, comportamiento por defecto del núcleo que aquí se rechaza explícitamente. Solo se consideran las configuraciones habilitadas (`enabled`); una configuración deshabilitada con fecha dentro del período bloqueado no bloquea el cálculo.

#### Scenario: Fecha de configuración dentro del período bloqueado

- **WHEN** la compañía tiene `fiscalyear_lock_date` igual o posterior a la fecha de una configuración habilitada
- **THEN** `calculate` lanza `ValidationError` antes de crear ningún asiento

#### Scenario: Fecha de configuración posterior al bloqueo

- **WHEN** la fecha de la configuración es estrictamente posterior a la fecha de bloqueo efectiva del diario
- **THEN** el cálculo no es bloqueado por esta verificación

#### Scenario: Configuración deshabilitada dentro del período bloqueado

- **WHEN** una configuración con `enabled = False` tiene fecha dentro del período bloqueado
- **THEN** `calculate` no lanza error por esa configuración y no genera ningún asiento para ella

### Requirement: Año por defecto del cierre

El campo `year` DEBE (MUST) tomar por defecto el año de `fiscalyear_lock_date` de la compañía activa (o del día de hoy si la compañía no tiene fecha de bloqueo), restándole un año únicamente cuando el mes de esa fecha es menor que `fiscalyear_last_month` **y además** su día es menor que `fiscalyear_last_day` (`_default_year` usa `and`, no `or`).

#### Scenario: Fecha de bloqueo anterior al cierre fiscal

- **WHEN** la compañía cierra el 31/12 y su `fiscalyear_lock_date` es 2025-03-31 (mes 3 < 12 pero día 31 no es menor que 31)
- **THEN** el campo `year` de un cierre nuevo se propone como 2025, no como 2024

### Requirement: Sin solapamiento de períodos de cierre por compañía

El sistema DEBE (MUST) validar, mediante el constraint Python `_check_period_overlap` (disparado sobre `date_start`, `date_end`, `date_opening`, `company_id` y `state`), que un cierre no activo (`state != 'cancelled'`) cumpla `date_start <= date_end < date_opening`, y que su rango `[date_start, date_end]` no se solape con el de ningún otro cierre no cancelado de la misma compañía. El solape se evalúa con límites inclusivos en ambos extremos (`date_start <= other.date_end` y `date_end >= other.date_start`): un cierre que empieza el mismo día en que otro termina se considera solapado. Esto reemplaza el antiguo `unique(year, company_id)`, permitiendo así varios cierres por año para una misma compañía (por ejemplo, cierres semestrales) mientras sus fechas no se crucen. Los cierres cancelados no se tienen en cuenta ni como origen ni como destino de la comparación. La búsqueda de cierres solapados no usa `sudo()`, de modo que el `name` de un cierre de otra compañía nunca se filtra en el mensaje de error.

#### Scenario: Cierres no solapados en el mismo año permitidos

- **WHEN** se crean dos cierres para la misma compañía y año con rangos de fechas que no se cruzan (p. ej. primer y segundo semestre)
- **THEN** ambos se crean sin error

#### Scenario: Cierres solapados en la misma compañía

- **WHEN** se crea un cierre cuyo rango de fechas se cruza con el de un cierre existente no cancelado de la misma compañía
- **THEN** se lanza `ValidationError` y el cierre no se crea

#### Scenario: Contacto borde a borde entre dos cierres

- **WHEN** un cierre nuevo empieza (`date_start`) el mismo día en que termina (`date_end`) un cierre existente de la misma compañía
- **THEN** se considera solapamiento y se lanza `ValidationError`

#### Scenario: Cierres solapados en compañías distintas

- **WHEN** dos cierres con el mismo rango de fechas pertenecen a compañías distintas
- **THEN** ninguno bloquea al otro

#### Scenario: Un cierre cancelado no cuenta para el solapamiento

- **WHEN** existe un cierre cancelado cuyo rango se cruzaría con el de un cierre nuevo
- **THEN** el cierre nuevo se crea sin error, ignorando el cierre cancelado

### Requirement: Carga de la configuración desde plantilla

Al seleccionar `closing_template_id`, el onchange DEBE (MUST) vaciar `move_config_ids` y reconstruirlo a partir de la plantilla (leída con `with_company(company_id)`): copia `check_draft_moves` y, por cada configuración de plantilla, `name`, `sequence`, `code`, `move_type`, `closing_type_default`, los mapeos y los tipos de cierre, forzando `enabled = True`. El campo `inverse` NO se copia (está comentado en `_prepare_config`), por lo que las configuraciones cargadas desde plantilla nunca traen referencia inversa. La fecha del asiento se fija en `date_end` si `move_date` de la plantilla es `last_ending` y en `date_opening` en cualquier otro caso; el diario es el `journal_id` de la plantilla (campo `company_dependent`) o, si está vacío, el diario de la compañía con código `MISC` y si no existe el primer diario de tipo `general`. La cuenta destino de cada mapeo se resuelve buscando por `=ilike` sobre el `code` entre las cuentas cuyo `company_ids` incluye la compañía del cierre, tomando la primera coincidencia; si no hay coincidencia, el nombre del mapeo se reemplaza por el mensaje "No destination account '%s' found." y el mapeo queda sin cuenta destino.

#### Scenario: Plantilla con fecha de fin de período

- **WHEN** se selecciona una plantilla cuyas configuraciones tienen `move_date = last_ending` y sin diario propio
- **THEN** las configuraciones cargadas quedan con `date` igual a `date_end` del cierre y el diario `MISC` de la compañía (o el primer diario general si `MISC` no existe)

#### Scenario: Cuenta destino inexistente

- **WHEN** un mapeo de la plantilla apunta a un patrón de cuenta destino sin coincidencias en la compañía
- **THEN** el mapeo se carga sin cuenta destino y con el nombre de error "No destination account ... found."

### Requirement: `template_id` opcional en la plantilla de configuración

`account.fiscalyear.closing.config.template.template_id` DEBE (MUST) permanecer sin `required=True`, de modo que una configuración de plantilla pueda crearse o guardarse de forma independiente (sin pasar por el formulario de la plantilla padre) con `template_id` vacío; al construirla desde el subformulario one2many de una plantilla, `template_id` se completa igualmente por el propio mecanismo del one2many.

#### Scenario: Configuración de plantilla independiente

- **WHEN** se crea directamente un `account.fiscalyear.closing.config.template` sin indicar `template_id`
- **THEN** el registro se crea correctamente con `template_id` vacío

#### Scenario: Configuración añadida desde el formulario de la plantilla

- **WHEN** se añade una línea de configuración al campo `move_config_ids` de una plantilla mediante su formulario
- **THEN** la línea se guarda con `template_id` apuntando a la plantilla, sin error de campo obligatorio

### Requirement: Cálculo de las fechas del ejercicio a partir del año

Al cambiar el campo `year`, el onchange DEBE (MUST) recalcular `date_end` como `year-fiscalyear_last_month-fiscalyear_last_day` de la compañía (ambos con `zfill(2)`), `date_start` como un año antes más un día, y `date_opening` como el día siguiente a `date_end`. El `name` se compone como "date_start-date_end" solo cuando ambas fechas difieren; si coincidieran, `name` queda con la fecha de fin sola.

#### Scenario: Año fiscal natural

- **WHEN** se introduce el año 2024 en una compañía con cierre fiscal al 31/12
- **THEN** `date_start` queda en 2024-01-01, `date_end` en 2024-12-31, `date_opening` en 2025-01-01 y `name` en "2024-01-01-2024-12-31"

### Requirement: Generación de asientos por mapeo de cuentas

Por cada configuración habilitada con mapeos, `moves_create` DEBE (MUST) construir un asiento (`account.move`) con `ref` = nombre de la configuración, `date`, `fyc_id`, `closing_type` = `move_type` y diario de la configuración, cuyas líneas provienen de `_mapping_move_lines_get`: por cada cuenta origen que coincide (`=ilike`) con el patrón `src_accounts`, según el tipo de cierre resuelto para su `account_type` (`closing_type_get`, con `closing_type_default` como respaldo) se genera una línea que revierte el saldo del período (`balance`, débitos menos créditos de las líneas cuyo asiento no está en `cancel`, entre `date_start` y `date_end`) o líneas agrupadas por partner (`unreconciled`, cuyo `read_group` no excluye los asientos cancelados); los tipos de cierre distintos de `balance`/`unreconciled` se omiten, los saldos cero no generan línea y el acumulado por cuenta destino se registra como línea de contrapartida con nombre "Result". La fecha de las líneas es `date_opening` cuando el `move_type` de la configuración es `opening` y `date_end` en el resto de los casos.

#### Scenario: Cuenta de resultado con saldo

- **WHEN** una configuración con tipo de cierre `balance` procesa una cuenta origen con débitos 0 y créditos 1000 en el período, mapeada a una cuenta destino
- **THEN** el asiento incluye una línea que debita 1000 en la cuenta origen y una línea "Result" que acredita 1000 en la cuenta destino

#### Scenario: Cuenta sin movimientos

- **WHEN** una cuenta origen del mapeo no tiene saldo en el período
- **THEN** no se genera línea para esa cuenta

#### Scenario: Cierre por partner

- **WHEN** el tipo de cierre resuelto para la cuenta es `unreconciled`
- **THEN** se genera una línea por cada partner con saldo distinto de cero, agrupando débitos y créditos del período incluidos los asientos cancelados

### Requirement: Normalización de la cuenta destino en los mapeos

`account.fiscalyear.closing.mapping` DEBE (MUST) sobrescribir `create` y `write` para normalizar `dest_account_id` a un id simple antes de delegar en el `super()`, aceptando indistintamente un entero, una lista/tupla (se toma el primer elemento, o `False` si está vacía) o un recordset/valor con atributo `id` (se toma `.id`). El comportamiento es simétrico entre `create` (recibe una lista de `vals`) y `write` (recibe un único `vals`).

#### Scenario: Cambio de cuenta destino desde el formulario

- **WHEN** un usuario cambia la cuenta destino de un mapeo ya guardado y el cliente envía `{"dest_account_id": 42}`
- **THEN** el `write` guarda `dest_account_id = 42` sin error

#### Scenario: Creación programática con recordset

- **WHEN** se crea un mapeo pasando `dest_account_id` como un recordset de `account.account` (por ejemplo desde `_prepare_mapping`)
- **THEN** el `create` normaliza el valor a su `id` antes de guardar

### Requirement: Asiento inverso de apertura

Una configuración sin mapeos pero con `inverse` DEBE (MUST) generar su asiento como reverso (`_reverse_moves`) del asiento de la configuración cuyo `code` coincide con `inverse` dentro del mismo cierre, fechado en `date_opening` cuando el `move_type` es `opening` y en `date_end` en caso contrario, y con el diario de la propia configuración; sobre el asiento reverso se escriben después `ref` (nombre de la configuración) y `closing_type`. Si la configuración referenciada no existe o todavía no tiene `move_id`, `inverse_move_prepare` devuelve `False.ids` y el cálculo aborta con `AttributeError`. El campo `inverse` está comentado tanto en la lista como en el formulario de `move_config_ids` en `view_account_fiscalyear_closing_form` y tampoco se copia desde la plantilla, de modo que en la práctica solo puede llegar por creación programática.

#### Scenario: Apertura como reverso del cierre

- **WHEN** se calcula una configuración de tipo `opening` cuyo campo `inverse` apunta al código de la configuración de cierre ya generada
- **THEN** se crea el asiento reverso del asiento de cierre con fecha `date_opening` y se guarda en `move_id` de la configuración

#### Scenario: Referencia inversa sin asiento previo

- **WHEN** la configuración con `inverse` se calcula antes que la configuración referenciada, o el código no existe en el cierre
- **THEN** el cálculo termina con `AttributeError` en lugar de generar el reverso

### Requirement: Detección de asiento descuadrado

Cuando la diferencia absoluta redondeada a 2 decimales entre el total de créditos y débitos del asiento preparado es mayor o igual a 0.01, `moves_create` DEBE (MUST) abstenerse de crear el asiento y devolver `(False, data)`, y `calculate` DEBE (MUST) crear el wizard `account.fiscalyear.closing.unbalanced.move` con esos datos (descartando las claves `closing_type` y `fyc_id`) y devolver su acción; en ese caso `button_calculate` ejecuta `_moves_remove` sobre los asientos intermedios ya creados y no cambia el estado.

#### Scenario: Descuadre detectado

- **WHEN** el asiento preparado para una configuración tiene débitos y créditos que difieren en 0.01 o más
- **THEN** se muestra el wizard "Unbalanced journal entry found", se cancelan/eliminan los asientos ya generados (nunca se borra uno posteado) y el cierre permanece en `draft`

### Requirement: Publicación de los asientos de cierre

`button_post` DEBE (MUST) recorrer `move_config_ids` ordenadas por `sequence` ascendente —incluidas las deshabilitadas— y llamar `action_post()` sobre el `move_id` de cada una (sin efecto cuando está vacío), y escribir `posted` en el cierre sin comprobar su estado anterior.

#### Scenario: Publicar el cierre calculado

- **WHEN** se pulsa el botón de publicar sobre un cierre calculado
- **THEN** los asientos de las configuraciones con `move_id` se postean en orden de secuencia y el estado pasa a `posted`

### Requirement: Cancelación y recálculo sin eliminar asientos posteados

`_moves_remove` DEBE (MUST) separar los asientos generados por el cierre en dos grupos: los que llegaron a estar `posted` y el resto. Sobre los posteados, primero desconcilia sus líneas conciliadas (`remove_move_reconcile`) y luego llama `button_cancel()` de `account.move` (que internamente hace la transición `posted -> draft -> cancel`); esos asientos **nunca se eliminan** de la base de datos, quedan en estado `cancel`. Sobre el resto (asientos que nunca llegaron a postearse: `draft` o `calculated`), desconcilia sus líneas conciliadas y los elimina con `unlink()`, para que un recálculo no acumule asientos cancelados basura. `button_cancel` invoca `_moves_remove` y deja el cierre en `cancelled`; `button_recalculate` invoca `_moves_remove` y luego `button_calculate`, generando asientos nuevos que reemplazan a los eliminados (los que sí se postearon quedan cancelados y conviven con los nuevos).

#### Scenario: Cancelar un cierre con un asiento ya posteado

- **WHEN** se cancela un cierre cuyo único asiento generado fue posteado, con líneas conciliadas
- **THEN** las conciliaciones se deshacen, el asiento pasa a estado `cancel` (sigue existiendo en la base de datos) y el cierre queda en `cancelled`

#### Scenario: Recalcular un cierre con un asiento posteado

- **WHEN** se ejecuta `button_recalculate` sobre un cierre cuyo asiento generado fue posteado
- **THEN** el asiento original queda cancelado (no eliminado), se genera un asiento nuevo distinto en estado `draft` y el cierre vuelve a `calculated`

#### Scenario: Cancelar un cierre con asientos no posteados

- **WHEN** se cancela un cierre cuyos asientos generados nunca se postearon
- **THEN** esos asientos se eliminan de la base de datos y el cierre queda en `cancelled`

### Requirement: Borrado restringido por estado

El sistema DEBE (MUST) impedir eliminar un registro de `account.fiscalyear.closing` cuyo estado no sea `draft` ni `cancelled`, lanzando `UserError`.

#### Scenario: Borrar un cierre calculado

- **WHEN** se intenta eliminar un cierre en estado `calculated` o `posted`
- **THEN** se lanza un error y el registro no se elimina

### Requirement: Código único por cierre y por plantilla

El sistema DEBE (MUST) exigir, vía constraint SQL `code_uniq`, que el campo `code` de las configuraciones sea único dentro de un mismo cierre (`account.fiscalyear.closing.config` por `fyc_id`) y dentro de una misma plantilla (`account.fiscalyear.closing.config.template` por `template_id`).

#### Scenario: Código duplicado en un cierre

- **WHEN** se crean dos configuraciones con el mismo `code` para el mismo cierre
- **THEN** la segunda creación es rechazada por la restricción de unicidad

### Requirement: Regla multicompañía sobre cierres y plantillas

El sistema DEBE (MUST) aplicar record rules globales (`fiscalyear_closing_multi_company_rule` y `fiscalyear_closing_template_multi_company_rule`, cargadas con `noupdate="1"`) que limitan la visibilidad de `account.fiscalyear.closing` y `account.fiscalyear.closing.template` a registros sin compañía o cuya `company_id` esté entre las compañías activas del usuario (`company_ids`).

#### Scenario: Cierre de otra compañía

- **WHEN** un usuario sin acceso a la compañía X consulta los cierres fiscales
- **THEN** los cierres de la compañía X no aparecen en los resultados
