# account_fiscal_year_closing

## Purpose

Asistente genérico de cierre de año fiscal (origen OCA account-closing, Tecnativa). Define los modelos concretos `account.fiscalyear.closing` (el cierre de un ejercicio), `account.fiscalyear.closing.config` (cada asiento a generar), `account.fiscalyear.closing.mapping` (mapeo de cuentas origen → destino), `account.fiscalyear.closing.type` (tipo de cierre por tipo de cuenta) y sus contrapartes plantilla (`account.fiscalyear.closing.template`, `...config.template`, `...mapping.template`, `...type.template`). Depende de `account`. Los modelos concretos heredan de los abstractos `account.fiscalyear.closing.abstract`, `account.fiscalyear.closing.config.abstract`, `account.fiscalyear.closing.mapping.abstract` y `account.fiscalyear.closing.type.abstract`, cuya definición no vive en este repositorio; igualmente el wizard `account.fiscalyear.closing.unbalanced.move` se invoca desde este módulo pero su definición base no está en estas fuentes. La extensión venezolana del proceso vive en `l10n_ve_account_fiscalyear_closing`.

## Requirements

### Requirement: Flujo de estados del cierre

El registro de cierre (`account.fiscalyear.closing`) DEBE (MUST) manejar el ciclo de estados `draft` → `calculated` → `posted`, con `cancelled` como salida y `button_recover` como retorno a borrador: `button_calculate` pasa a `calculated` y estampa `calculation_date` solo si el cálculo fue exitoso; `button_cancel` pasa a `cancelled`; `button_recover` regresa a `draft` limpiando `calculation_date`.

#### Scenario: Cálculo exitoso

- **WHEN** se pulsa `button_calculate` y todos los asientos configurados se generan balanceados
- **THEN** el cierre queda en estado `calculated` con `calculation_date` en la fecha/hora actual

#### Scenario: Recuperación a borrador

- **WHEN** se pulsa `button_recover` sobre un cierre
- **THEN** el cierre vuelve a estado `draft` y `calculation_date` queda vacío

### Requirement: Verificación de asientos en borrador antes de calcular

Cuando el flag `check_draft_moves` está activo, el método `calculate` DEBE (MUST) ejecutar `draft_moves_check`, que lanza `ValidationError` listando ID, fecha, número y referencia de cada `account.move` en estado `draft` de la compañía cuyo `date` cae dentro de `date_start`–`date_end`.

#### Scenario: Existen borradores en el período

- **WHEN** se calcula un cierre con `check_draft_moves` activo y hay al menos un asiento en borrador dentro del período
- **THEN** se lanza un error de validación que enumera los asientos en borrador y no se genera ningún asiento de cierre

### Requirement: Carga de la configuración desde plantilla

Al seleccionar `closing_template_id`, el onchange DEBE (MUST) reconstruir `move_config_ids` a partir de la plantilla: copia `check_draft_moves`, y por cada configuración de plantilla copia secuencia, código, tipo de asiento, mapeos y tipos de cierre; la fecha del asiento se fija en `date_end` si `move_date` de la plantilla es `last_ending` o en `date_opening` si es `first_opening`; el diario es el de la plantilla o, en su defecto, el diario de la compañía con código `MISC` y si no existe el primer diario de tipo `general`. La cuenta destino de cada mapeo se resuelve buscando por patrón `=ilike` sobre el código (`dest_account` de la plantilla) tomando la primera coincidencia; si no hay coincidencia, el nombre del mapeo se reemplaza por el mensaje "No destination account '%s' found.".

#### Scenario: Plantilla con fecha de fin de período

- **WHEN** se selecciona una plantilla cuyas configuraciones tienen `move_date = last_ending` y sin diario propio
- **THEN** las configuraciones cargadas quedan con `date` igual a `date_end` del cierre y el diario `MISC` de la compañía (o el primer diario general si `MISC` no existe)

#### Scenario: Cuenta destino inexistente

- **WHEN** un mapeo de la plantilla apunta a un patrón de cuenta destino sin coincidencias en la compañía
- **THEN** el mapeo se carga sin cuenta destino y con el nombre de error "No destination account ... found."

### Requirement: Cálculo de las fechas del ejercicio a partir del año

Al cambiar el campo `year`, el onchange DEBE (MUST) recalcular `date_end` con el último mes/día fiscal de la compañía (`fiscalyear_last_month`, `fiscalyear_last_day`), `date_start` como un año antes más un día, `date_opening` como el día siguiente a `date_end`, y el `name` del cierre como "date_start-date_end".

#### Scenario: Año fiscal natural

- **WHEN** se introduce el año 2024 en una compañía con cierre fiscal al 31/12
- **THEN** `date_start` queda en 2024-01-01, `date_end` en 2024-12-31 y `date_opening` en 2025-01-01

### Requirement: Generación de asientos por mapeo de cuentas

Por cada configuración habilitada con mapeos, `moves_create` DEBE (MUST) construir un asiento (`account.move`) con referencia, fecha, `fyc_id`, `closing_type` y diario de la configuración, cuyas líneas provienen de `_mapping_move_lines_get`: por cada cuenta origen que coincide (`=ilike`) con el patrón `src_accounts`, según el tipo de cierre resuelto para su `account_type` (`closing_type_get`, con `closing_type_default` como respaldo) se genera una línea que revierte el saldo del período (`balance`, sumando débitos menos créditos de las líneas no canceladas entre `date_start` y `date_end`) o líneas agrupadas por partner (`unreconciled`); los saldos cero se omiten y el acumulado por cuenta destino se registra como línea de contrapartida con nombre "Result".

#### Scenario: Cuenta de resultado con saldo

- **WHEN** una configuración con tipo de cierre `balance` procesa una cuenta origen con débitos 0 y créditos 1000 en el período, mapeada a una cuenta destino
- **THEN** el asiento incluye una línea que debita 1000 en la cuenta origen y una línea "Result" que acredita 1000 en la cuenta destino

#### Scenario: Cuenta sin movimientos

- **WHEN** una cuenta origen del mapeo no tiene saldo en el período
- **THEN** no se genera línea para esa cuenta

#### Scenario: Cierre por partner

- **WHEN** el tipo de cierre resuelto para la cuenta es `unreconciled`
- **THEN** se genera una línea por cada partner con saldo distinto de cero, agrupando débitos y créditos del período

### Requirement: Asiento inverso de apertura

Una configuración sin mapeos pero con `inverse` DEBE (MUST) generar su asiento como reverso (`_reverse_moves`) del asiento de la configuración cuyo código coincide con `inverse` dentro del mismo cierre, fechado en `date_opening` cuando el `move_type` es `opening` y en `date_end` en caso contrario, asignándole la referencia y el `closing_type` de la configuración.

#### Scenario: Apertura como reverso del cierre

- **WHEN** se calcula una configuración de tipo `opening` cuyo campo `inverse` apunta al código de la configuración de cierre ya generada
- **THEN** se crea el asiento reverso del asiento de cierre con fecha `date_opening`

### Requirement: Detección de asiento descuadrado

Cuando la diferencia absoluta entre el total de débitos y créditos del asiento preparado es mayor o igual a 0.01, `moves_create` DEBE (MUST) abstenerse de crear el asiento y `calculate` DEBE (MUST) devolver la acción del wizard `account.fiscalyear.closing.unbalanced.move` con los datos del asiento; en ese caso `button_calculate` elimina los asientos intermedios ya creados y no cambia el estado.

#### Scenario: Descuadre detectado

- **WHEN** el asiento preparado para una configuración tiene débitos y créditos que difieren en 0.01 o más
- **THEN** se muestra el wizard "Unbalanced journal entry found", se eliminan los asientos ya generados y el cierre permanece en `draft`

### Requirement: Publicación de los asientos de cierre

`button_post` DEBE (MUST) publicar (`action_post`) el asiento de cada configuración en orden ascendente de `sequence` y dejar el cierre en estado `posted`.

#### Scenario: Publicar el cierre calculado

- **WHEN** se pulsa el botón de publicar sobre un cierre calculado
- **THEN** los asientos de las configuraciones se postean en orden de secuencia y el estado pasa a `posted`

### Requirement: Cancelación con eliminación de asientos

`button_cancel` y `button_recalculate` DEBEN (MUST) eliminar los asientos generados por el cierre vía `_moves_remove`: se rompe la conciliación de las líneas conciliadas, los asientos se cancelan (`button_cancel` de `account.move`) y se borran; la cancelación deja el cierre en `cancelled` y el recálculo vuelve a ejecutar el cálculo completo.

#### Scenario: Cancelar un cierre calculado

- **WHEN** se cancela un cierre con asientos generados, algunos con líneas conciliadas
- **THEN** las conciliaciones se deshacen, los asientos se eliminan y el cierre queda en `cancelled`

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

El sistema DEBE (MUST) aplicar record rules globales (`fiscalyear_closing_multi_company_rule` y `fiscalyear_closing_template_multi_company_rule`) que limitan la visibilidad de `account.fiscalyear.closing` y `account.fiscalyear.closing.template` a registros sin compañía o cuya `company_id` esté entre las compañías del usuario.

#### Scenario: Cierre de otra compañía

- **WHEN** un usuario sin acceso a la compañía X consulta los cierres fiscales
- **THEN** los cierres de la compañía X no aparecen en los resultados
