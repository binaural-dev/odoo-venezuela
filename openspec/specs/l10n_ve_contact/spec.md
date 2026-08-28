# l10n_ve_contact

## Purpose

Adapta los contactos (`res.partner`) a la identificación fiscal venezolana: prefijo de RIF/cédula, autocompletado del nombre desde el registro electoral del CNE, controles de duplicidad de RIF y email, e inmutabilidad del nombre cuando el contacto tiene transacciones. Extiende `res.partner`, `res.company` y `res.config.settings`, y usa el helper compartido `tools/binaural_cne_query.py` del repositorio, importado como `from ...tools import binaural_cne_query` (es decir, resuelto como `odoo.addons.tools`, con la raíz del repositorio en el addons path). Depende de `base`, `contacts`, `account`, `l10n_ve_rate` y `l10n_ve_location` (los campos de municipio/parroquia/ciudad que este módulo marca con tracking se definen en `l10n_ve_location`).

## Requirements

### Requirement: Prefijo de identificación fiscal

Cada contacto DEBE (MUST) tener un campo `prefix_vat` de selección con los valores `V`, `E`, `J`, `G`, `P` y `C`, con `V` como valor por defecto y `tracking=True`, mostrado junto al `vat` en el formulario de contacto.

#### Scenario: Contacto nuevo

- **WHEN** se abre el formulario de un contacto nuevo
- **THEN** el prefijo aparece preseleccionado en `V` junto al campo de RIF/cédula

### Requirement: Autocompletado del nombre desde el CNE

El sistema DEBE (MUST) consultar el registro electoral del CNE (`http://www.cne.gov.ve/web/registro_electoral/ce.php`, helper `binaural_cne_query.get_default_name_by_vat`, timeout de 5 s, parseo con BeautifulSoup) y asignar el nombre obtenido en dos puntos: (a) en el onchange `_onchange_` de `vat`/`prefix_vat`, solo cuando hay `vat`, `name` está vacío y `prefix_vat` es `V` o `E`, validando antes con `_check_vat` que el `vat` solo contenga dígitos (si no, `MissingError` "The vat field only accepts numbers"); y (b) en `create`, cuando los valores traen `vat` sin `name` y `prefix_vat` es exactamente `V` (la condición `prefix_vat == "V" and ... and prefix_vat in ["V","E"]` deja fuera a `E`). Si el helper captura una excepción devuelve `("", False)` y el llamador no asigna nombre, dejando el error solo en el log.

#### Scenario: Cédula venezolana en el formulario

- **WHEN** un usuario escribe una cédula con prefijo `V` o `E` en un contacto sin nombre y el CNE responde con los datos del elector
- **THEN** el campo `name` se llena con el nombre devuelto por el CNE

#### Scenario: Cédula con caracteres no numéricos

- **WHEN** en el onchange el contacto no tiene nombre, el prefijo es `V` o `E` y el `vat` contiene caracteres que no son dígitos
- **THEN** se lanza `MissingError` indicando que el campo solo acepta números

#### Scenario: CNE inaccesible

- **WHEN** la consulta al CNE falla por timeout, error de conexión o HTML inesperado dentro del `try` del helper
- **THEN** el helper devuelve `("", False)`, el nombre no se asigna y el error solo queda en el log

#### Scenario: Respuesta del CNE sin filas de tabla

- **WHEN** el CNE responde 200 pero el HTML no contiene ninguna fila `<tr>` con los datos del elector, de modo que el helper llega al final de la función y devuelve `None`
- **THEN** el desempaquetado `name, flag = get_default_name_by_vat(...)` falla con `TypeError` y la creación o el onchange del contacto aborta

### Requirement: Unicidad de RIF/cédula

El sistema DEBE (MUST) rechazar, vía `check_duplicate_vat`, la existencia de otro contacto con el mismo par `prefix_vat`+`vat`. El control se dispara en `create` cuando los valores incluyen `prefix_vat` (la condición escrita es `if "vat" and "prefix_vat" in vals`, que Python evalúa solo como `"prefix_vat" in vals`) y en `write` cuando incluyen `vat` (`if "prefix_vat" and "vat" in vals`), en este último caso **después** de haber ejecutado el `super().write()`. El cuerpo solo actúa si ambos valores recibidos son verdaderos: un `write` que cambie el `vat` sin enviar también `prefix_vat` no valida nada, porque el prefijo se lee de los valores y nunca del registro. La búsqueda excluye el propio registro y, cuando la compañía activa tiene `validate_user_creation_by_company`, se limita a `company_id` = la compañía indicada o la activa; en cualquier otro caso es global. Ninguno de los dos flags desactiva la validación: `validate_user_creation_general` solo cambia el texto del mensaje de error, y con ambos flags en `False` el control sigue aplicándose de forma global.

#### Scenario: RIF duplicado

- **WHEN** se crea un contacto enviando `prefix_vat` y un `vat` que ya existen en otro contacto dentro del alcance configurado
- **THEN** se lanza `ValidationError` y el contacto no se crea

#### Scenario: Validación por compañía

- **WHEN** `validate_user_creation_by_company` está activo y el RIF duplicado pertenece a un contacto de otra compañía o a un contacto sin compañía (`company_id` vacío)
- **THEN** la creación es permitida, porque el dominio exige coincidencia exacta de compañía

#### Scenario: Ambos flags desactivados

- **WHEN** la compañía tiene `validate_user_creation_by_company` y `validate_user_creation_general` en `False` y se crea un contacto con un RIF ya usado en cualquier compañía
- **THEN** la creación se rechaza igualmente: el control es global y no configurable

#### Scenario: Cambio de RIF sin enviar el prefijo

- **WHEN** un `write` modifica solo `vat`
- **THEN** `check_duplicate_vat` recibe `prefix_vat` vacío y no comprueba duplicados

### Requirement: Duplicidad de email en contactos

El sistema DEBE (MUST) rechazar, vía `check_duplicate_email`, que se guarde un `res.partner` de tipo `contact` con un email que ya tenga **cualquier** otro partner (el dominio filtra por `email` e `id`, sin filtrar por `type`): en `create` cuando los valores traen `email` y el `type` es `contact` (o no viene), y en `write` cuando traen `email`, evaluando el `type` de cada registro y después del `super().write()`. Igual que en el RIF, los flags de compañía solo determinan si la búsqueda se restringe a `company_id` o es global y qué mensaje se muestra; nunca desactivan el control.

#### Scenario: Email repetido

- **WHEN** se guarda un contacto de tipo `contact` con un email que ya tiene otro partner dentro del alcance configurado, aunque ese otro partner sea una dirección de entrega o una compañía
- **THEN** se lanza `ValidationError`

#### Scenario: Dirección de entrega

- **WHEN** se crea un registro con `type` distinto de `contact` (por ejemplo una dirección de entrega) con un email repetido
- **THEN** la validación de email no se aplica a ese registro

### Requirement: Los controles de create se omiten si falla la consulta al CNE

En `create`, cuando el registro trae `vat` sin `name` con prefijo `V` y el helper del CNE devuelve `flag = False`, el bucle ejecuta `continue`, por lo que el sistema DEBE (MUST) saltar para ese registro el resto de las validaciones de la iteración: no se ejecutan `check_duplicate_vat` ni `check_duplicate_email` y el contacto se crea sin verificar duplicados.

#### Scenario: CNE caído al crear un contacto sin nombre

- **WHEN** se crea un contacto con `vat`, sin `name`, con `prefix_vat` = `V` y la consulta al CNE falla
- **THEN** el contacto se crea sin nombre y sin que se comprueben RIF ni email duplicados

### Requirement: Inmutabilidad del nombre con transacciones

Cuando la **compañía activa del usuario** tiene `validate_partner_name_immutable` (por defecto `True`, configurable vía campo related en `res.config.settings`), la constraint `_check_name_immutable` (`@api.constrains("name")`) DEBE (MUST) impedir guardar el `name` de un contacto que tenga registros asociados en `sale.order`, `purchase.order`, `account.move` (limitado a `move_type` en `out_invoice`/`in_invoice`) o `account.move.line`, saltando los modelos que no estén en el registro. Como el chequeo de `account.move.line` solo filtra por `partner_id`, cualquier apunte contable del partner —incluidos pagos y asientos que no son facturas— basta para bloquear el cambio.

#### Scenario: Contacto con facturas

- **WHEN** se intenta renombrar un contacto que es partner de al menos una factura o de cualquier apunte contable
- **THEN** se lanza `ValidationError` indicando que no se puede modificar el nombre de un contacto con transacciones asociadas

#### Scenario: Control desactivado

- **WHEN** la compañía activa del usuario tiene `validate_partner_name_immutable` en `False`
- **THEN** el nombre puede modificarse aunque existan transacciones, incluso si la compañía dueña del contacto sí tiene el control activo

### Requirement: País por defecto Venezuela

El campo `country_id` de `res.partner` DEBE (MUST) tener como valor por defecto Venezuela (`base.ve`) y `tracking=True`.

#### Scenario: Contacto nuevo

- **WHEN** se crea un contacto sin indicar país
- **THEN** el país queda establecido en Venezuela

### Requirement: Compañía por defecto en contactos

El campo `company_id` de `res.partner` DEBE (MUST) tener como valor por defecto la compañía activa del usuario (`_default_company_id`).

#### Scenario: Contacto creado en multicompañía

- **WHEN** un usuario con compañía activa X crea un contacto sin indicar compañía
- **THEN** el contacto queda asignado a la compañía X

### Requirement: Partner propio al crear una compañía

Al crear una `res.company`, el `create` sobrescrito DEBE (MUST) crear primero su partner con `name` tomado obligatoriamente de `vals["name"]`, `is_company = False`, `image_1920` = el `logo` recibido, y `email`, `phone`, `website`, `vat` y `country_id` de la compañía; después le pone `company_id = False` y lo asigna como `partner_id` de la compañía nueva. Una creación de compañía sin la clave `name` en los valores falla con `KeyError`.

#### Scenario: Alta de compañía

- **WHEN** se crea una compañía nueva con nombre
- **THEN** su partner se crea con `is_company = False`, `company_id` en falso (visible desde todas las compañías) y queda asignado a `partner_id`

### Requirement: Bloqueo de eliminación de contactos

El módulo DEBE (MUST) sobrescribir la ACL `base.access_res_partner_group_partner_manager` dejando `perm_unlink = 0` (con lectura, escritura y creación en 1), de modo que ni siquiera los administradores de contactos (`base.group_partner_manager`) puedan eliminar registros de `res.partner`.

#### Scenario: Intento de borrado

- **WHEN** un usuario del grupo de administración de contactos intenta eliminar un contacto
- **THEN** la operación es rechazada por falta de permiso de eliminación

### Requirement: Seguimiento de cambios en los datos del contacto

Los campos clave del contacto DEBEN (MUST) registrar sus cambios en el chatter (`tracking=True`): `name`, `mobile`, `street`, `street2`, `zip`, `country_id`, `state_id`, `city_id`, `municipality`, `parish_id`, `prefix_vat`, y las propiedades comerciales `property_supplier_payment_term_id`, `property_payment_term_id`, `property_product_pricelist` y `property_account_position_id`.

#### Scenario: Cambio de dirección

- **WHEN** un usuario modifica la calle o el estado de un contacto
- **THEN** el cambio queda registrado como valor anterior/nuevo en el chatter del contacto

### Requirement: Datos obligatorios en el formulario de contacto

La vista `res_partner_l10n_ve_form_contacts` DEBE (MUST) eliminar el `vat` de su posición original y volver a colocarlo junto a `prefix_vat` (sin etiqueta, con placeholder "CI/RIF: 12345678") marcándolo `required="1"`, y agregar `required="1"` a `street`, `country_id` y `state_id`.

#### Scenario: Guardado sin RIF

- **WHEN** un usuario intenta guardar un contacto sin `vat` desde el formulario de contactos
- **THEN** el formulario impide guardar hasta llenar el campo
