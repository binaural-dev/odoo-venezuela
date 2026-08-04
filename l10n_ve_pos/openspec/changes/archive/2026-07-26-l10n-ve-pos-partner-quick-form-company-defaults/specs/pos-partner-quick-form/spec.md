# Spec delta: pos-partner-quick-form

## ADDED Requirements

### Requirement: El PdV usa una vista form reducida de res.partner, sin modificar el form de backoffice

El PdV SHALL usar una vista form de `res.partner` propia y reducida
(`l10n_ve_pos.view_partner_form_pos`), derivada `mode="primary"` de
`base.view_partner_form`, de modo que el arch de la vista form de
backoffice permanezca sin modificar.

#### Scenario: Crear contacto desde el PdV

- **GIVEN** un cajero en el PdV que abre "Crear cliente" (sin
  `resId`)
- **WHEN** se renderiza el diálogo de la acción
  `point_of_sale.res_partner_action_edit_pos`
- **THEN** el formulario mostrado es el reducido: sin pestañas, sin
  foto, sin etiquetas; visible el aviso de RIF duplicado,
  `company_type`, `name`, `email`, `phone`, `prefix_vat` + `vat`, el
  bloque de dirección venezolano (calle, calle 2, país, C.P., estado,
  ciudad, municipio, parroquia) y `barcode`

#### Scenario: Abrir el mismo contacto en el backoffice

- **GIVEN** un contacto creado o editado desde el PdV
- **WHEN** un usuario lo abre desde Contactos en el backoffice (no desde
  el PdV)
- **THEN** ve el formulario completo de `base.view_partner_form`, con
  todas sus pestañas, foto, propiedades y campos — intacto, sin ningún
  recorte del PdV

#### Scenario: Editar un contacto existente desde el PdV

- **GIVEN** un contacto ya existente, con `resId` conocido
- **WHEN** el cajero lo abre para editar desde el PdV
- **THEN** se le muestra el mismo formulario reducido que al crear, con
  los valores ya guardados del contacto (no se disparan defaults de
  compañía sobre campos ya poblados)

### Requirement: Los contactos nuevos creados desde el PdV se precargan con la dirección de la compañía

Al crear un contacto **nuevo** desde el PdV, el sistema SHALL precargar
`country_id`, `state_id`, `city_id`, `municipality`, `parish_id` y `zip`
con los valores correspondientes de `env.company.partner_id`, salvo que
ya exista un valor resuelto por otra vía (contexto `default_*` explícito,
default de campo, o herencia desde un `parent_id`).

#### Scenario: Compañía con dirección completa

- **GIVEN** la compañía activa tiene `partner_id` con `country_id`,
  `state_id`, `city_id`, `municipality`, `parish_id` y `zip` todos
  poblados
- **WHEN** el cajero crea un contacto nuevo desde el PdV
- **THEN** los seis campos del formulario reducido aparecen precargados
  con los valores del partner de la compañía

#### Scenario: Compañía con zip vacío

- **GIVEN** la compañía activa tiene `partner_id` con `zip` vacío
  (falsy) pero el resto de campos de localización poblados
- **WHEN** el cajero crea un contacto nuevo desde el PdV
- **THEN** `zip` queda vacío en el formulario y el resto de campos de
  localización sí se precargan — no se interrumpe el `default_get` por
  un campo faltante

#### Scenario: default_* explícito en el contexto

- **GIVEN** la acción o el flujo que abre el formulario ya trae, por
  ejemplo, `default_state_id` en el contexto
- **WHEN** se calcula el `default_get` del contacto nuevo
- **THEN** `state_id` conserva el valor ya resuelto por `super()`
  (el `default_state_id` del contexto), y el `default_get` de
  `l10n_ve_pos` no lo sobreescribe con el de la compañía

#### Scenario: Contacto hijo (dirección de entrega/facturación)

- **GIVEN** el formulario se abre para crear un contacto hijo, con
  `default_parent_id` presente en el contexto (o `parent_id` ya resuelto
  por `super()`)
- **WHEN** se calcula el `default_get`
- **THEN** ninguno de los seis campos de localización se precarga desde
  la compañía — el contacto hijo hereda la dirección de su padre por el
  mecanismo nativo, no de la compañía

#### Scenario: Creación desde el backoffice, sin el flag de contexto

- **GIVEN** un usuario crea un `res.partner` nuevo desde Contactos en el
  backoffice (el contexto no trae `l10n_ve_pos_partner_defaults`)
- **WHEN** se calcula el `default_get`
- **THEN** ningún campo de localización se precarga desde la compañía —
  el comportamiento nativo de Odoo queda sin cambios

### Requirement: El campo city (Char) nunca se escribe por el mecanismo de defaults

El sistema SHALL NUNCA escribir el campo `city` (Char,
`related="city_id.name"`, `store=True`, escribible) desde el mecanismo
de defaults de compañía, porque escribirlo directamente renombraría el
registro `res.country.city` referenciado por `city_id`.

#### Scenario: Precarga de city_id no renombra ninguna ciudad

- **GIVEN** el `default_get` precarga `city_id` con la ciudad de la
  compañía
- **WHEN** se inspeccionan las claves devueltas por el `default_get`
- **THEN** la clave `city` NO está presente entre los valores por
  defecto, y ningún registro `res.country.city` es modificado como
  efecto colateral — `city` (Char) se completa solo, vía el related
  almacenado, en cuanto `city_id` queda fijado
