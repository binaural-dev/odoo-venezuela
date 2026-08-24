# account_fiscal_year_closing

## Purpose

Asistente genérico de cierre de año fiscal (origen OCA account-closing, Tecnativa). Define los modelos concretos `account.fiscalyear.closing` (el cierre de un ejercicio), `account.fiscalyear.closing.config` (cada asiento a generar), `account.fiscalyear.closing.mapping` (mapeo de cuentas origen → destino), `account.fiscalyear.closing.type` (tipo de cierre por tipo de cuenta) y sus contrapartes plantilla (`account.fiscalyear.closing.template`, `...config.template`, `...mapping.template`, `...type.template`). Depende de `account`. Los modelos concretos heredan de los abstractos `account.fiscalyear.closing.abstract`, `account.fiscalyear.closing.config.abstract`, `account.fiscalyear.closing.mapping.abstract` y `account.fiscalyear.closing.type.abstract`, cuya definición no vive en este repositorio; igualmente el wizard `account.fiscalyear.closing.unbalanced.move` se invoca desde este módulo pero su definición base no está en estas fuentes. La extensión venezolana del proceso vive en `l10n_ve_account_fiscalyear_closing`.

Nota de estado (rama actual): tampoco existen en estas fuentes los campos `fyc_id` y `closing_type` de `account.move`, aunque el módulo los usa como `inverse_name` de `move_ids`, los escribe en `move_prepare` y los muestra en `views/account_move_views.xml`. El módulo no tiene `__init__.py` ni `models/__init__.py`, y su `__manifest__.py` declara dos archivos que no existen en el árbol (`security/ir.model.access.csv` y `wizards/account_fiscal_year_closing_unbalanced_move_views.xml`); solo está presente `security/account_fiscalyear_closing_security.xml`. Por tanto el módulo, tal como está en esta rama, no es instalable y no aporta ACL propias: los requirements de abajo describen la lógica contenida en `models/`, no un despliegue verificado. Varios campos usan el atributo `states={...}` (retirado de Odoo desde la 17), que hoy es inerte: lo que gobierna la edición por estado son los atributos `readonly="state != 'draft'"` de las vistas.

## Requirements

### Requirement: Flujo de estados del cierre

El registro de cierre (`account.fiscalyear.closing`) DEBE (MUST) manejar los estados `draft`, `calculated` (etiqueta "Processed"), `posted` y `cancelled`: `button_calculate` pasa a `calculated` y estampa `calculation_date` solo si el cálculo devolvió `True`; `button_cancel` elimina los asientos y pasa a `cancelled`; `button_recover` escribe `draft` y limpia `calculation_date`. Los métodos no validan el estado de origen: es la vista formulario la que expone `button_calculate` solo en `draft`, `button_recalculate` y `button_post` solo en `calculated`, `button_cancel` en `calculated` o `posted`, y `button_recover` únicamente en `cancelled`.

#### Scenario: Cálculo exitoso

- **WHEN** se pulsa `button_calculate` y `calculate` devuelve `True` (todos los asientos configurados se generaron balanceados)
- **THEN** el cierre queda en estado `calculated` con `calculation_date` en la fecha/hora actual

#### Scenario: Recuperación a borrador

- **WHEN** se pulsa `button_recover` sobre un cierre cancelado (único estado donde el botón es visible)
- **THEN** el cierre vuelve a estado `draft` y `calculation_date` queda vacío

### Requirement: Verificación de asientos en borrador antes de calcular

Cuando el flag `check_draft_moves` está activo, el método `calculate` DEBE (MUST) ejecutar `draft_moves_check`, que lanza `ValidationError` listando ID, fecha, número y referencia de cada `account.move` en estado `draft` de la compañía cuyo `date` cae dentro de `date_start`–`date_end`.

#### Scenario: Existen borradores en el período

- **WHEN** se calcula un cierre con `check_draft_moves` activo y hay al menos un asiento en borrador dentro del período
- **THEN** se lanza un error de validación que enumera los asientos en borrador y no se genera ningún asiento de cierre

### Requirement: Año por defecto del cierre

El campo `year` DEBE (MUST) tomar por defecto el año de `fiscalyear_lock_date` de la compañía activa (o del día de hoy si la compañía no tiene fecha de bloqueo), restándole un año únicamente cuando el mes de esa fecha es menor que `fiscalyear_last_month` **y además** su día es menor que `fiscalyear_last_day` (`_default_year` usa `and`, no `or`).

#### Scenario: Fecha de bloqueo anterior al cierre fiscal

- **WHEN** la compañía cierra el 31/12 y su `fiscalyear_lock_date` es 2025-03-31 (mes 3 < 12 pero día 31 no es menor que 31)
- **THEN** el campo `year` de un cierre nuevo se propone como 2025, no como 2024

### Requirement: Carga de la configuración desde plantilla

Al seleccionar `closing_template_id`, el onchange DEBE (MUST) vaciar `move_config_ids` y reconstruirlo a partir de la plantilla (leída con `with_company(company_id)`): copia `check_draft_moves` y, por cada configuración de plantilla, `name`, `sequence`, `code`, `move_type`, `closing_type_default`, los mapeos y los tipos de cierre, forzando `enabled = True`. El campo `inverse` NO se copia (la línea está comentada en `_prepare_config`), por lo que las configuraciones cargadas desde plantilla nunca traen referencia inversa. La fecha del asiento se fija en `date_end` si `move_date` de la plantilla es `last_ending` y en `date_opening` en cualquier otro caso; el diario es el `journal_id` de la plantilla (campo `company_dependent`) o, si está vacío, el diario de la compañía con código `MISC` y si no existe el primer diario de tipo `general`. La cuenta destino de cada mapeo se resuelve buscando por `=ilike` sobre el `code` entre las cuentas cuyo `company_ids` incluye la compañía del cierre, tomando la primera coincidencia; si no hay coincidencia, el nombre del mapeo se reemplaza por el mensaje "No destination account '%s' found." y el mapeo queda sin cuenta destino.

#### Scenario: Plantilla con fecha de fin de período

- **WHEN** se selecciona una plantilla cuyas configuraciones tienen `move_date = last_ending` y sin diario propio
- **THEN** las configuraciones cargadas quedan con `date` igual a `date_end` del cierre y el diario `MISC` de la compañía (o el primer diario general si `MISC` no existe)

#### Scenario: Cuenta destino inexistente

- **WHEN** un mapeo de la plantilla apunta a un patrón de cuenta destino sin coincidencias en la compañía
- **THEN** el mapeo se carga sin cuenta destino y con el nombre de error "No destination account ... found."

#### Scenario: Plantilla con configuración inversa

- **WHEN** la plantilla tiene una configuración de apertura cuyo campo `inverse` apunta al código del cierre
- **THEN** la configuración se carga con `inverse` vacío y, si tampoco tiene mapeos, al calcular no genera ningún asiento

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

`account.fiscalyear.closing.mapping` DEBE (MUST) sobrescribir `create` y `write` para normalizar `dest_account_id`: en `create` la reasignación es un no-op (`vals["dest_account_id"] = vals["dest_account_id"]`), mientras que en `write` toma el primer elemento del valor recibido (`vals["dest_account_id"][0]`), lo que solo funciona si el valor llega como lista o recordset; un `write` con el entero que envía el cliente web falla con `TypeError`.

#### Scenario: Cambio de cuenta destino desde el formulario

- **WHEN** un usuario cambia la cuenta destino de un mapeo ya guardado y el cliente envía `{"dest_account_id": 42}`
- **THEN** el `write` intenta indexar el entero y la operación termina en `TypeError`, sin guardar el cambio

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
- **THEN** se muestra el wizard "Unbalanced journal entry found", se eliminan los asientos ya generados y el cierre permanece en `draft`

### Requirement: Publicación de los asientos de cierre

`button_post` DEBE (MUST) recorrer `move_config_ids` ordenadas por `sequence` ascendente —incluidas las deshabilitadas— y llamar `action_post()` sobre el `move_id` de cada una (sin efecto cuando está vacío), y escribir `posted` en el cierre sin comprobar su estado anterior.

#### Scenario: Publicar el cierre calculado

- **WHEN** se pulsa el botón de publicar sobre un cierre calculado
- **THEN** los asientos de las configuraciones con `move_id` se postean en orden de secuencia y el estado pasa a `posted`

### Requirement: Cancelación con eliminación de asientos

`button_cancel` y `button_recalculate` DEBEN (MUST) eliminar los asientos generados por el cierre vía `_moves_remove`: se rompe la conciliación de las líneas conciliadas (`remove_move_reconcile`), los asientos se cancelan (`button_cancel` de `account.move`) y se borran; la cancelación deja el cierre en `cancelled` y el recálculo continúa con `button_calculate`.

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

El sistema DEBE (MUST) aplicar record rules globales (`fiscalyear_closing_multi_company_rule` y `fiscalyear_closing_template_multi_company_rule`, cargadas con `noupdate="1"`) que limitan la visibilidad de `account.fiscalyear.closing` y `account.fiscalyear.closing.template` a registros sin compañía o cuya `company_id` esté entre las compañías activas del usuario (`company_ids`).

#### Scenario: Cierre de otra compañía

- **WHEN** un usuario sin acceso a la compañía X consulta los cierres fiscales
- **THEN** los cierres de la compañía X no aparecen en los resultados
