# l10n_ve_location

## Purpose

Aporta la división político-territorial de Venezuela: modelos maestros de municipios (`res.country.municipality`) y parroquias (`res.country.parish`), la data precargada de estados, municipios y parroquias del país, los campos correspondientes en el contacto (`res.partner`) y la reescritura del bloque de dirección del formulario de contacto. Las ciudades son las de Odoo (`res.city`, del módulo `base_address_extended`): desde 20 el módulo ya no tiene un modelo de ciudades propio. Depende de `base`, `contacts` y `base_address_extended`, declara `pre_init_hook` y publica las ciudades y los dos catálogos como menús bajo `contacts.menu_localisation` sin restricción de grupos. `l10n_ve_contact` agrega tracking sobre los campos que este módulo define en el contacto.

## Requirements

### Requirement: Las ciudades son las de Odoo

El catálogo de ciudades DEBE (MUST) ser el modelo `res.city` de Odoo (`base_address_extended`, que Odoo 20 instala siempre con `account`): nombre y país obligatorios, estado opcional y código postal opcional. La entrada de menú Contactos → Localización → Cities (acción `action_res_country_city`, que conserva su id porque otros módulos la usan) DEBE (MUST) abrir `res.city` con las vistas de Odoo. En 19 el módulo tenía su propio modelo `res.country.city`, con estado obligatorio y una restricción de unicidad por nombre, estado y país; `res.city` no tiene esa restricción y muestra el código postal junto al nombre si se carga.

#### Scenario: Abrir el catálogo de ciudades

- **WHEN** un usuario interno entra a Contactos → Localización → Cities
- **THEN** ve la lista de ciudades de Odoo (`res.city`), con su país, estado y código postal

#### Scenario: Ciudad con el mismo nombre, estado y país

- **WHEN** se crea una ciudad con un nombre ya registrado para el mismo estado y país
- **THEN** la ciudad se guarda, porque `res.city` no tiene restricción de unicidad (en 19 se rechazaba)

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

El contacto (`res.partner`) DEBE (MUST) contar con los campos `city_id` (Many2one a `res.city`, el campo que define `base_address_extended`; el módulo solo le pone la etiqueta "City"), `municipality` (Many2one a `res.country.municipality`) y `parish_id` (Many2one a `res.country.parish`, con domain de campo `[('municipality_id', '=', municipality)]`), y el campo estándar `city` se redefine como related almacenado de `city_id.name` (etiqueta "City related"), es decir deja de ser un texto libre. `city` DEBE (MUST) seguir siendo texto plano, no traducible, aunque el nombre de `res.city` sí lo sea.

#### Scenario: Selección de parroquia

- **WHEN** un usuario selecciona un municipio en el contacto y despliega el campo de parroquia
- **THEN** solo se ofrecen las parroquias de ese municipio

#### Scenario: Ciudad como texto

- **WHEN** se asigna una ciudad en `city_id`
- **THEN** el campo `city` del contacto refleja el nombre de esa ciudad y no puede escribirse directamente

#### Scenario: Ciudad con nombre traducido

- **WHEN** una ciudad de `res.city` tiene su nombre traducido a otro idioma
- **THEN** `city` del contacto guarda un único texto, el nombre de la ciudad, sin traducciones

### Requirement: Dirección venezolana obligatoria en el formulario de contacto

La vista `view_form_res_partner_inherited` DEBE (MUST) ocultar (`invisible="1"`) el bloque estándar `o_address_format` del formulario de contacto y sustituirlo por un bloque propio con `street`, `street2`, `country_id`, `zip`, `state_id`, `city_id`, `municipality` y `parish_id`, donde `city_id`, `municipality` y `parish_id` son **obligatorios** (`required="1"`) y los dos primeros se filtran por el estado seleccionado (`[('state_id', '=', state_id)]`); `city` se muestra invisible. En las direcciones hijas (pestaña "Contacts & Addresses") DEBE (MUST) reemplazar `city` por `city_id`, agregar `municipality` y `parish_id`, y hacer obligatorios `street`, `zip`, `country_id`, `state_id`, `city_id`, `municipality` y `parish_id` cuando el `type` de la dirección no es `contact`.

#### Scenario: Guardar un contacto sin municipio

- **WHEN** un usuario intenta guardar un contacto desde el formulario sin ciudad, municipio o parroquia
- **THEN** el formulario impide guardar hasta llenar los tres campos

#### Scenario: Dirección de entrega

- **WHEN** se captura una dirección hija de tipo distinto de `contact`
- **THEN** calle, código postal, país, estado, ciudad, municipio y parroquia son obligatorios en ese subformulario

### Requirement: Data geográfica de Venezuela precargada

El módulo DEBE (MUST) cargar como data 25 registros de `res.country.state` con país `base.ve` y su código (p. ej. "Distrito Capital"/DC), 334 `res.country.municipality` (cada uno con un único estado asignado vía `[(6, 0, [ref(...)])]` y `country_id` = `base.ve`) y 1319 `res.country.parish` vinculadas a su municipio. El módulo **no** carga ciudades (`res.city`): si ningún otro módulo las carga, el catálogo de ciudades de Venezuela queda vacío tras la instalación, aunque el formulario de contacto exija `city_id`.

#### Scenario: Instalación del módulo

- **WHEN** se instala `l10n_ve_location`
- **THEN** quedan disponibles los 25 estados, 334 municipios y 1319 parroquias de Venezuela

#### Scenario: Primer contacto tras instalar

- **WHEN** un usuario captura un contacto recién instalado el módulo y abre el desplegable de ciudad
- **THEN** no hay ninguna ciudad para elegir y debe crearla antes de poder guardar el contacto

### Requirement: Acceso de los usuarios internos a los catálogos

La ACL del módulo DEBE (MUST) otorgar a los usuarios internos (`base.group_user`) permisos completos (leer, escribir, crear y eliminar) sobre `res.city`, `res.country.municipality`, `res.country.parish` y `res.partner.zone`, y los menús Cities / Municipalities / Parish / Zone se publican bajo Contactos → Localización sin restricción adicional de grupo.

`res.city` es un modelo de Odoo, que por sí solo deja administrar las ciudades únicamente a los administradores de contactos. El permiso completo para todo usuario interno es intencional: conserva lo que permitía 19 con `res.country.city`, porque el formulario de contacto exige una ciudad y el catálogo nace vacío, y quien captura el contacto tiene que poder crearla. Un usuario que no es interno (portal) DEBE (MUST) seguir sin poder crear, modificar ni eliminar ciudades.

#### Scenario: Usuario interno gestiona catálogos

- **WHEN** un usuario interno sin permisos de administrador de contactos crea, modifica o elimina una ciudad, municipio o parroquia
- **THEN** la operación es permitida por la ACL

#### Scenario: Usuario de portal intenta gestionar ciudades

- **WHEN** un usuario de portal intenta crear, modificar o eliminar una ciudad
- **THEN** Odoo lanza un error de acceso (`AccessError`) y la ciudad no cambia

### Requirement: Migración de identificadores desde binaural_location

El `pre_init_hook` del módulo DEBE (MUST) ejecutar tres `UPDATE ir_model_data SET module='l10n_ve_location' WHERE module='binaural_location' AND name LIKE ...` con los prefijos `res_country_state_`, `res_country_parish_` y `res_country_municipality_`, evitando duplicar la data en bases que migran desde el módulo anterior. El hook recibe el `env` y le pasa `env.cr` a las funciones auxiliares, que ejecutan el SQL sobre ese cursor.

#### Scenario: Base con el módulo antiguo

- **WHEN** se instala `l10n_ve_location` en una base que ya tenía la data cargada por `binaural_location`
- **THEN** los registros existentes pasan a estar identificados bajo `l10n_ve_location` y la carga de data no los duplica

#### Scenario: Ciudades del módulo antiguo

- **WHEN** la base migrada tenía xml_ids con otro prefijo (por ejemplo de ciudades)
- **THEN** el hook no los reasigna, porque solo cubre estados, parroquias y municipios

### Requirement: Las ciudades de 19 pasan a las ciudades de Odoo

Al actualizar el módulo a 20.0.1.0.1 o posterior en una base que tiene la tabla `res_country_city` (una base que viene de 19, o una de 20 creada antes de este cambio), la migración previa DEBE (MUST):

- copiar cada ciudad a `res.city` con su nombre, país y estado, o reusar una ciudad de `res.city` que ya tenga el mismo nombre, estado y país;
- hacer que toda columna que apuntaba a una ciudad vieja (la ciudad de los contactos y la de cualquier otro módulo) apunte a su ciudad nueva;
- pasar los identificadores externos (xmlid) de las ciudades viejas a sus ciudades nuevas;
- borrar la tabla `res_country_city`, porque Odoo no borra la tabla de un modelo que ya no está en el código.

En una base que no tiene la tabla, la migración no hace nada.

#### Scenario: Contactos con ciudad en una base que viene de 19

- **WHEN** se actualiza `l10n_ve_location` en una base cuyos contactos tienen ciudades de `res.country.city`
- **THEN** cada contacto conserva su ciudad, ahora como registro de `res.city`, y la tabla `res_country_city` deja de existir

#### Scenario: La ciudad ya existe en Odoo

- **WHEN** una ciudad vieja tiene el mismo nombre, estado y país que una ciudad que ya está en `res.city`
- **THEN** no se crea una ciudad repetida: los contactos pasan a apuntar a la que ya existía

#### Scenario: Orden de la actualización

- **WHEN** una base de 20 todavía tiene las ciudades viejas
- **THEN** la primera actualización tiene que ser la de `l10n_ve_location` (el build normal de Odoo.sh), no `update all`; mientras tanto `l10n_ve_base` conserva la clave de `city_id` hacia las ciudades viejas para que actualizar otros módulos no falle (ver la spec de `l10n_ve_base`)
