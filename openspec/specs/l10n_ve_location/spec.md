# l10n_ve_location

## Purpose

Aporta la división político-territorial de Venezuela: modelos maestros de ciudades (`res.country.city`), municipios (`res.country.municipality`) y parroquias (`res.country.parish`), la data precargada de estados, municipios y parroquias del país, los campos correspondientes en el contacto (`res.partner`) y la reescritura del bloque de dirección del formulario de contacto. Depende de `base` y `contacts`, declara `pre_init_hook` y publica los tres catálogos como menús bajo `contacts.menu_localisation` sin restricción de grupos. `l10n_ve_contact` agrega tracking sobre los campos que este módulo define en el contacto.

## Requirements

### Requirement: Catálogo de ciudades único por estado y país

El modelo `res.country.city` DEBE (MUST) exigir nombre, país y estado, e impedir vía constraint SQL `name_uniq` (`unique (name, country_id, state_id)`) registrar dos ciudades con el mismo nombre para el mismo estado y país.

#### Scenario: Ciudad duplicada

- **WHEN** se crea una ciudad con un nombre ya registrado para el mismo estado y país
- **THEN** la creación es rechazada por la restricción de unicidad

### Requirement: Catálogo de municipios único y normalizado

El modelo `res.country.municipality` DEBE (MUST) exigir `code`, `name`, `country_id` y `state_id` —este último es un **Many2many** a `res.country.state`, no un Many2one—, ofrecer `active` (archivable, por defecto `True`), normalizar el nombre a mayúsculas sin espacios extremos en el onchange `on_change_state` de `name`, y rechazar con `ValidationError` "The municipality is already registered" (constraint Python `constraint_unique_municipality` sobre `country_id`, `state_id` y `name`) otro municipio con el mismo nombre, país y estado. Como la constraint compara `record.state_id.id`, solo puede evaluarse cuando el municipio tiene exactamente un estado vinculado.

#### Scenario: Nombre en minúsculas

- **WHEN** un usuario escribe el nombre de un municipio en minúsculas
- **THEN** el nombre se convierte a mayúsculas sin espacios extremos al salir del campo

#### Scenario: Municipio duplicado

- **WHEN** se guarda un municipio con nombre, país y estado ya registrados en otro municipio
- **THEN** se lanza el error "The municipality is already registered"

#### Scenario: Municipio con varios estados

- **WHEN** se guarda un municipio con dos o más estados en `state_id`
- **THEN** la constraint falla al pedir `.id` sobre un recordset múltiple ("Expected singleton") en lugar de validar la unicidad

### Requirement: Parroquias vinculadas a un municipio

El modelo `res.country.parish` DEBE (MUST) exigir `name`, `code` y el municipio (`municipality_id`, Many2one a `res.country.municipality`) al que pertenece la parroquia. No define unicidad de nombre ni de código.

#### Scenario: Parroquia sin municipio

- **WHEN** se intenta crear una parroquia sin municipio
- **THEN** la creación es rechazada por el campo requerido

#### Scenario: Parroquias homónimas

- **WHEN** se crean dos parroquias con el mismo nombre y código en municipios distintos, o incluso en el mismo municipio
- **THEN** ambas se guardan, porque el modelo no tiene restricción de unicidad

### Requirement: Ubicación venezolana en el contacto

El contacto (`res.partner`) DEBE (MUST) contar con los campos `city_id` (Many2one a `res.country.city`), `municipality` (Many2one a `res.country.municipality`) y `parish_id` (Many2one a `res.country.parish`, con domain de campo `[('municipality_id', '=', municipality)]`), y el campo estándar `city` se redefine como related almacenado de `city_id.name` (etiqueta "City related"), es decir deja de ser un texto libre.

#### Scenario: Selección de parroquia

- **WHEN** un usuario selecciona un municipio en el contacto y despliega el campo de parroquia
- **THEN** solo se ofrecen las parroquias de ese municipio

#### Scenario: Ciudad como texto

- **WHEN** se asigna una ciudad en `city_id`
- **THEN** el campo `city` del contacto refleja el nombre de esa ciudad y no puede escribirse directamente

### Requirement: Dirección venezolana obligatoria en el formulario de contacto

La vista `view_form_res_partner_inherited` DEBE (MUST) ocultar (`invisible="1"`) el bloque estándar `o_address_format` del formulario de contacto y sustituirlo por un bloque propio con `street`, `street2`, `country_id`, `zip`, `state_id`, `city_id`, `municipality` y `parish_id`, donde `city_id`, `municipality` y `parish_id` son **obligatorios** (`required="1"`) y los dos primeros se filtran por el estado seleccionado (`[('state_id', '=', state_id)]`); `city` se muestra invisible. En las direcciones hijas (pestaña "Contacts & Addresses") DEBE (MUST) reemplazar `city` por `city_id`, agregar `municipality` y `parish_id`, y hacer obligatorios `street`, `zip`, `country_id`, `state_id`, `city_id`, `municipality` y `parish_id` cuando el `type` de la dirección no es `contact`.

#### Scenario: Guardar un contacto sin municipio

- **WHEN** un usuario intenta guardar un contacto desde el formulario sin ciudad, municipio o parroquia
- **THEN** el formulario impide guardar hasta llenar los tres campos

#### Scenario: Dirección de entrega

- **WHEN** se captura una dirección hija de tipo distinto de `contact`
- **THEN** calle, código postal, país, estado, ciudad, municipio y parroquia son obligatorios en ese subformulario

### Requirement: Data geográfica de Venezuela precargada

El módulo DEBE (MUST) cargar como data 25 registros de `res.country.state` con país `base.ve` y su código (p. ej. "Distrito Capital"/DC), 334 `res.country.municipality` (cada uno con un único estado asignado vía `[(6, 0, [ref(...)])]` y `country_id` = `base.ve`) y 1319 `res.country.parish` vinculadas a su municipio. **No** se precarga ninguna `res.country.city`: el catálogo de ciudades queda vacío tras la instalación, aunque el formulario de contacto exija `city_id`.

#### Scenario: Instalación del módulo

- **WHEN** se instala `l10n_ve_location`
- **THEN** quedan disponibles los 25 estados, 334 municipios y 1319 parroquias de Venezuela

#### Scenario: Primer contacto tras instalar

- **WHEN** un usuario captura un contacto recién instalado el módulo y abre el desplegable de ciudad
- **THEN** no hay ninguna ciudad para elegir y debe crearla antes de poder guardar el contacto

### Requirement: Acceso de los usuarios internos a los catálogos

La ACL del módulo DEBE (MUST) otorgar a los usuarios internos (`base.group_user`) permisos completos (leer, escribir, crear y eliminar) sobre `res.country.city`, `res.country.municipality` y `res.country.parish`, y los menús Cities / Municipalities / Parish se publican bajo Contactos → Localización sin restricción adicional de grupo.

#### Scenario: Usuario interno gestiona catálogos

- **WHEN** un usuario interno crea, modifica o elimina una ciudad, municipio o parroquia
- **THEN** la operación es permitida por la ACL

### Requirement: Migración de identificadores desde binaural_location

El `pre_init_hook` del módulo DEBE (MUST) ejecutar tres `UPDATE ir_model_data SET module='l10n_ve_location' WHERE module='binaural_location' AND name LIKE ...` con los prefijos `res_country_state_`, `res_country_parish_` y `res_country_municipality_`, evitando duplicar la data en bases que migran desde el módulo anterior. El hook recibe el `env` y le pasa `env.cr` a las funciones auxiliares, que ejecutan el SQL sobre ese cursor.

#### Scenario: Base con el módulo antiguo

- **WHEN** se instala `l10n_ve_location` en una base que ya tenía la data cargada por `binaural_location`
- **THEN** los registros existentes pasan a estar identificados bajo `l10n_ve_location` y la carga de data no los duplica

#### Scenario: Ciudades del módulo antiguo

- **WHEN** la base migrada tenía xml_ids con otro prefijo (por ejemplo de ciudades)
- **THEN** el hook no los reasigna, porque solo cubre estados, parroquias y municipios
