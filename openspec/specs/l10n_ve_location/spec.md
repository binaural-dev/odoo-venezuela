# l10n_ve_location

## Purpose

Aporta la división político-territorial de Venezuela: modelos maestros de ciudades (`res.country.city`), municipios (`res.country.municipality`) y parroquias (`res.country.parish`), la data precargada de estados, municipios y parroquias del país, y los campos correspondientes en el contacto (`res.partner`). Depende de `base` y `contacts`. `l10n_ve_contact` agrega tracking sobre los campos que este módulo define en el contacto.

## Requirements

### Requirement: Catálogo de ciudades único por estado y país

El modelo `res.country.city` DEBE (MUST) exigir nombre, país y estado, e impedir vía constraint SQL `name_uniq` registrar dos ciudades con el mismo nombre para el mismo estado y país.

#### Scenario: Ciudad duplicada

- **WHEN** se crea una ciudad con un nombre ya registrado para el mismo estado y país
- **THEN** la creación es rechazada por la restricción de unicidad

### Requirement: Catálogo de municipios único y normalizado

El modelo `res.country.municipality` DEBE (MUST) exigir código, nombre, país y estados; normalizar el nombre a mayúsculas sin espacios extremos en el onchange de `name`; e impedir, vía constraint `constraint_unique_municipality`, registrar dos municipios con el mismo nombre para el mismo país y estado.

#### Scenario: Nombre en minúsculas

- **WHEN** un usuario escribe el nombre de un municipio en minúsculas
- **THEN** el nombre se convierte a mayúsculas al salir del campo

#### Scenario: Municipio duplicado

- **WHEN** se guarda un municipio con nombre, país y estado ya registrados en otro municipio
- **THEN** se lanza el error "The municipality is already registered"

### Requirement: Parroquias vinculadas a un municipio

El modelo `res.country.parish` DEBE (MUST) exigir nombre, código y el municipio (`municipality_id`) al que pertenece la parroquia.

#### Scenario: Parroquia sin municipio

- **WHEN** se intenta crear una parroquia sin municipio
- **THEN** la creación es rechazada por el campo requerido

### Requirement: Ubicación venezolana en el contacto

El contacto (`res.partner`) DEBE (MUST) contar con los campos `city_id` (Many2one a `res.country.city`), `municipality` (Many2one a `res.country.municipality`) y `parish_id` (Many2one a `res.country.parish`), donde las parroquias seleccionables se filtran por el municipio elegido (domain `[('municipality_id', '=', municipality)]`), y el campo estándar `city` se mantiene como related almacenado de `city_id.name`.

#### Scenario: Selección de parroquia

- **WHEN** un usuario selecciona un municipio en el contacto y despliega el campo de parroquia
- **THEN** solo se ofrecen las parroquias de ese municipio

#### Scenario: Ciudad como texto

- **WHEN** se asigna una ciudad en `city_id`
- **THEN** el campo `city` del contacto refleja el nombre de esa ciudad

### Requirement: Data geográfica de Venezuela precargada

El módulo DEBE (MUST) cargar como data los 25 registros de estados venezolanos (`res.country.state` con país `base.ve` y su código, p. ej. "Distrito Capital"/DC), 334 municipios y 1319 parroquias, disponibles al instalar.

#### Scenario: Instalación del módulo

- **WHEN** se instala `l10n_ve_location`
- **THEN** los estados, municipios y parroquias de Venezuela quedan disponibles en los catálogos correspondientes

### Requirement: Acceso de los usuarios internos a los catálogos

La ACL del módulo DEBE (MUST) otorgar a los usuarios internos (`base.group_user`) permisos completos (leer, escribir, crear y eliminar) sobre `res.country.city`, `res.country.municipality` y `res.country.parish`.

#### Scenario: Usuario interno gestiona catálogos

- **WHEN** un usuario interno crea o modifica una ciudad, municipio o parroquia
- **THEN** la operación es permitida por la ACL

### Requirement: Migración de identificadores desde binaural_location

El `pre_init_hook` del módulo DEBE (MUST) reasignar en `ir_model_data` al módulo `l10n_ve_location` los xml_ids con prefijos `res_country_state_`, `res_country_parish_` y `res_country_municipality_` que pertenecían al módulo anterior `binaural_location`, evitando duplicar la data en bases que migran.

#### Scenario: Base con el módulo antiguo

- **WHEN** se instala `l10n_ve_location` en una base que ya tenía la data cargada por `binaural_location`
- **THEN** los registros existentes pasan a estar identificados bajo `l10n_ve_location` y la carga de data no los duplica
