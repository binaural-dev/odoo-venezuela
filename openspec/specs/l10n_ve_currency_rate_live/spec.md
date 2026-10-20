# l10n_ve_currency_rate_live

## Purpose

Agrega el Banco Central de Venezuela (BCV) como proveedor automático de tasas de cambio, obteniendo la tasa oficial del día desde el sitio web del BCV. Extiende `res.company` y `res.config.settings`. Depende de `l10n_ve_rate` (moneda alterna) y del módulo estándar `currency_rate_live` (infraestructura de sincronización de tasas por proveedor).

## Requirements

### Requirement: Proveedor de tasas BCV

El campo `currency_provider` de `res.company` DEBE (MUST) incluir la opción `bcv` ("Venezuelan Central Bank") entre los proveedores de sincronización de tasas disponibles.

#### Scenario: Selección del proveedor

- **WHEN** un administrador configura el proveedor de tasas de la compañía
- **THEN** la opción "Venezuelan Central Bank" está disponible en la selección

### Requirement: Obtención de tasas del día desde el sitio del BCV

El método `_get_bcv_currency_rates` DEBE (MUST) obtener del sitio `https://www.bcv.org.ve/` la cotización del día para las monedas activas del sistema entre EUR, CNY, TRY, RUB y USD, devolviendo un diccionario `{código: (tasa, fecha_actual)}`. Si no hay monedas activas de esa lista devuelve un diccionario vacío, y si ocurre un error de comunicación o parseo devuelve la tupla `(1, False)`.

#### Scenario: Consulta exitosa

- **WHEN** el sitio del BCV responde y hay monedas activas de la lista soportada
- **THEN** devuelve la tasa publicada de cada moneda activa con la fecha del día

#### Scenario: Error de comunicación

- **WHEN** la petición al sitio del BCV falla o el contenido no puede parsearse
- **THEN** devuelve `(1, False)` y registra el error en el log

### Requirement: Formateo de tasas como factor inverso con base VEF

El método `_parse_bcv_data` DEBE (MUST) devolver las tasas en el formato del framework de `currency_rate_live`: `VEF` con factor `1.0` como base, y cada moneda obtenida del BCV con factor `1.0/tasa`, incluyendo únicamente las tasas cuya fecha coincide con la fecha actual.

#### Scenario: Tasa del día

- **WHEN** el BCV devuelve una tasa con fecha igual a la fecha actual
- **THEN** el resultado incluye esa moneda con factor `1.0/tasa` junto a `VEF` en `1.0`

### Requirement: Bloqueo de sincronización automática en días no hábiles

La sincronización automática vía `_parse_bcv_data` DEBE (MUST) devolver un diccionario vacío (sin actualizar tasas) cuando el día actual es sábado o domingo y todas las compañías involucradas tienen activo el campo `can_update_habil_days` (por defecto `True`).

#### Scenario: Fin de semana con bloqueo activo

- **WHEN** el cron de sincronización corre un sábado o domingo y las compañías tienen `can_update_habil_days` activo
- **THEN** no se actualiza ninguna tasa

### Requirement: Bloqueo de actualización manual en días no hábiles

La acción manual `update_currency_rates_manually` de ajustes DEBE (MUST) lanzar un error cuando `can_update_habil_days` está activo y el día actual no es hábil (sábado o domingo).

#### Scenario: Actualización manual en fin de semana

- **WHEN** un usuario pulsa la actualización manual de tasas un sábado o domingo con `can_update_habil_days` activo
- **THEN** se lanza un error indicando que no se puede actualizar en día no hábil

### Requirement: Configuración del bloqueo por día hábil

El campo `can_update_habil_days` DEBE (MUST) ser configurable por compañía desde el bloque de tasa de cambio de la app "Binaural Settings" (campo related en `res.config.settings` con `readonly=False`), dentro de la sección "Exchange Rate Synchronization" que este módulo agrega a la vista de `l10n_ve_rate`.

#### Scenario: Desactivar el bloqueo

- **WHEN** un administrador desmarca "Only update in habil days" en ajustes y guarda
- **THEN** `can_update_habil_days` de la compañía queda en `False` y la sincronización corre también en fin de semana
