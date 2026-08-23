# l10n_ve_contact

## Purpose

Adapta los contactos (`res.partner`) a la identificación fiscal venezolana: prefijo de RIF/cédula, autocompletado del nombre desde el registro electoral del CNE, controles de duplicidad de RIF y email configurables por compañía, e inmutabilidad del nombre cuando el contacto tiene transacciones. Extiende `res.partner`, `res.company` y `res.config.settings`, y usa el helper compartido `tools/binaural_cne_query.py` del repositorio. Depende de `base`, `contacts`, `account`, `l10n_ve_rate` y `l10n_ve_location` (los campos de municipio/parroquia/ciudad que este módulo marca con tracking se definen en `l10n_ve_location`).

## Requirements

### Requirement: Prefijo de identificación fiscal

Cada contacto DEBE (MUST) tener un campo `prefix_vat` de selección con los valores `V`, `E`, `J`, `G`, `P` y `C`, con `V` como valor por defecto, mostrado junto al `vat` en el formulario de contacto.

#### Scenario: Contacto nuevo

- **WHEN** se abre el formulario de un contacto nuevo
- **THEN** el prefijo aparece preseleccionado en `V` junto al campo de RIF/cédula

### Requirement: Autocompletado del nombre desde el CNE

Cuando se captura una cédula sin nombre, el sistema DEBE (MUST) consultar el registro electoral del CNE (`http://www.cne.gov.ve/...`, helper `binaural_cne_query.get_default_name_by_vat`) y asignar el nombre obtenido: en el onchange de `vat`/`prefix_vat` para prefijos `V` y `E` (validando antes con `_check_vat` que el `vat` solo contenga números), y en `create` cuando el `vat` viene sin `name` y el prefijo es `V`. Si la consulta falla, el nombre no se asigna y el error solo se registra en el log.

#### Scenario: Cédula venezolana en el formulario

- **WHEN** un usuario escribe una cédula con prefijo `V` o `E` en un contacto sin nombre y el CNE responde
- **THEN** el campo `name` se llena con el nombre devuelto por el CNE

#### Scenario: Cédula con caracteres no numéricos

- **WHEN** en el onchange el `vat` contiene caracteres que no son dígitos
- **THEN** se lanza un error indicando que el campo solo acepta números

#### Scenario: CNE inaccesible

- **WHEN** la consulta al CNE falla (timeout o error de conexión)
- **THEN** el contacto se puede seguir capturando sin nombre autocompletado y no se propaga ningún error

### Requirement: Unicidad de RIF/cédula

El sistema DEBE (MUST) impedir, vía `check_duplicate_vat` (ejecutado en `create` cuando los valores incluyen `prefix_vat` y en `write` cuando incluyen `vat`), que exista otro contacto con el mismo par `prefix_vat`+`vat`: si la compañía tiene activo `validate_user_creation_by_company` la búsqueda se restringe a contactos de la misma compañía; en caso contrario la búsqueda es global. Ambos flags (`validate_user_creation_by_company`, `validate_user_creation_general`) se configuran por compañía vía campos related en `res.config.settings`.

#### Scenario: RIF duplicado en la misma compañía

- **WHEN** se crea un contacto con un `prefix_vat` y `vat` que ya existen en otro contacto visible según la configuración
- **THEN** se lanza un error de validación y el contacto no se crea

#### Scenario: Validación por compañía

- **WHEN** `validate_user_creation_by_company` está activo y el RIF duplicado pertenece a un contacto de otra compañía
- **THEN** la creación es permitida

### Requirement: Unicidad de email para contactos

El sistema DEBE (MUST) impedir, vía `check_duplicate_email`, que un contacto de tipo `contact` se cree o modifique con un email ya usado por otro contacto; con `validate_user_creation_by_company` activo la búsqueda se limita a la compañía, de lo contrario es global.

#### Scenario: Email repetido

- **WHEN** se guarda un contacto de tipo `contact` con un email que ya tiene otro contacto dentro del alcance configurado
- **THEN** se lanza un error de validación

#### Scenario: Dirección de entrega

- **WHEN** se crea un registro con `type` distinto de `contact` (por ejemplo una dirección de entrega) con un email repetido
- **THEN** la validación de email no se aplica

### Requirement: Inmutabilidad del nombre con transacciones

Cuando la compañía tiene activo `validate_partner_name_immutable` (por defecto `True`, configurable vía campo related en `res.config.settings`), el sistema DEBE (MUST) impedir cambiar el `name` de un contacto que tenga registros asociados en `sale.order`, `purchase.order`, `account.move` (facturas de cliente o proveedor) o `account.move.line` (constraint `_check_name_immutable`).

#### Scenario: Contacto con facturas

- **WHEN** se intenta renombrar un contacto que es partner de al menos una factura
- **THEN** se lanza un error indicando que no se puede modificar el nombre de un contacto con transacciones asociadas

#### Scenario: Control desactivado

- **WHEN** la compañía tiene `validate_partner_name_immutable` en `False`
- **THEN** el nombre puede modificarse aunque existan transacciones

### Requirement: País por defecto Venezuela

El campo `country_id` de `res.partner` DEBE (MUST) tener como valor por defecto Venezuela (`base.ve`).

#### Scenario: Contacto nuevo

- **WHEN** se crea un contacto sin indicar país
- **THEN** el país queda establecido en Venezuela

### Requirement: Compañía por defecto en contactos

El campo `company_id` de `res.partner` DEBE (MUST) tener como valor por defecto la compañía activa del usuario (`_default_company_id`).

#### Scenario: Contacto creado en multicompañía

- **WHEN** un usuario con compañía activa X crea un contacto sin indicar compañía
- **THEN** el contacto queda asignado a la compañía X

### Requirement: Partner propio al crear una compañía

Al crear una `res.company`, el `create` sobrescrito DEBE (MUST) crear explícitamente su partner con los datos de la compañía (nombre, logo como imagen, email, teléfono, website, `vat` y país), con `is_company = False` y `company_id` vacío, y vincularlo como `partner_id` de la compañía nueva.

#### Scenario: Alta de compañía

- **WHEN** se crea una compañía nueva
- **THEN** su partner se crea con `company_id` en falso (visible desde todas las compañías) y queda asignado a `partner_id`

### Requirement: Bloqueo de eliminación de contactos

El módulo DEBE (MUST) sobrescribir la ACL `base.access_res_partner_group_partner_manager` dejando `perm_unlink = 0`, de modo que ni siquiera los administradores de contactos (`base.group_partner_manager`) puedan eliminar registros de `res.partner`.

#### Scenario: Intento de borrado

- **WHEN** un usuario del grupo de administración de contactos intenta eliminar un contacto
- **THEN** la operación es rechazada por falta de permiso de eliminación

### Requirement: Seguimiento de cambios en los datos del contacto

Los campos clave del contacto DEBEN (MUST) registrar sus cambios en el chatter (`tracking=True`): `name`, `mobile`, `street`, `street2`, `zip`, `country_id`, `state_id`, `city_id`, `municipality`, `parish_id`, `prefix_vat`, y las propiedades comerciales `property_supplier_payment_term_id`, `property_payment_term_id`, `property_product_pricelist` y `property_account_position_id`.

#### Scenario: Cambio de dirección

- **WHEN** un usuario modifica la calle o el estado de un contacto
- **THEN** el cambio queda registrado como valor anterior/nuevo en el chatter del contacto

### Requirement: Datos obligatorios en el formulario de contacto

El formulario de contacto DEBE (MUST) exigir el llenado de `vat` (reubicado junto al prefijo), `street`, `country_id` y `state_id` (atributo `required` agregado por la vista `res_partner_l10n_ve_form_contacts`).

#### Scenario: Guardado sin RIF

- **WHEN** un usuario intenta guardar un contacto sin `vat` desde el formulario
- **THEN** el formulario impide guardar hasta llenar el campo
