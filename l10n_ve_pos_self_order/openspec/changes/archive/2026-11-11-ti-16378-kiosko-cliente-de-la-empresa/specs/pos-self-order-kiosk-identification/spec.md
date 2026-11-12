## MODIFIED Requirements

### Requirement: Búsqueda de contacto por cédula reutiliza el domain existente

El sistema SHALL buscar un `res.partner` por cédula con el mismo criterio de
coincidencia que `res.partner.check_duplicate_vat` (`prefix_vat` + `vat`),
entre los contactos que la caja puede facturar (ver "El Kiosko solo
identifica clientes que su caja puede facturar"). La respuesta de identificación y de
creación SHALL incluir, además de `id`/`name`/`phone`, la cédula que el propio
cliente tecleó (`vat`/`prefix_vat`) — no es información nueva para él.

#### Scenario: Cédula ya registrada

- **GIVEN** un `res.partner` existente con `prefix_vat='V'`, `vat='12345678'`
- **WHEN** el cliente teclea esa combinación en la pantalla de
  identificación del Kiosko
- **THEN** el servidor lo encuentra y devuelve `id`, `name`, `phone`, `vat` y
  `prefix_vat`, y el cliente pasa directo al catálogo con ese `partner_id`
  asignado a la orden

#### Scenario: Cédula no registrada

- **GIVEN** ninguna combinación `prefix_vat`+`vat` coincidente
- **WHEN** el cliente teclea una cédula nueva
- **THEN** el servidor responde "no encontrado" y el cliente ve el
  formulario de creación (nombre, apellido, teléfono) sin perder la cédula
  ya tecleada

#### Scenario: El endpoint de creación devuelve la cédula tecleada

- **GIVEN** un contacto recién creado desde el Kiosko
- **WHEN** el servidor responde al cliente tras la creación
- **THEN** la respuesta expone los mismos campos que la búsqueda (`id`,
  `name`, `phone`, `vat`, `prefix_vat`)

## ADDED Requirements

### Requirement: El Kiosko solo identifica clientes que su caja puede facturar

La búsqueda por cédula de las rutas `identify`, `identify/create` y
`set_phone` SHALL considerar solo los `res.partner` que la factura de la caja
acepta: los de la compañía de la caja, los de sus compañías padre y los
compartidos (`res.partner._check_company_domain(pos_config.company_id)`, la
misma regla con la que `account.move` valida el cliente). Un contacto de otra
empresa de la base SHALL tratarse como no encontrado.

#### Scenario: Cédula registrada solo en otra empresa

- **GIVEN** un `res.partner` con `prefix_vat='V'` y `vat='12345678'` de una
  empresa que no es la de la caja ni una de sus matrices
- **WHEN** el cliente se identifica con esa cédula en el Kiosko
- **THEN** `identify` no devuelve ese contacto y el Kiosko le pide registrarse;
  `set_phone` tampoco le completa el teléfono

#### Scenario: Cédula registrada en dos empresas

- **GIVEN** la misma cédula en un contacto de otra empresa (con el `id` más
  bajo) y en un contacto de la empresa de la caja
- **WHEN** el cliente se identifica con esa cédula
- **THEN** `identify` devuelve el contacto de la empresa de la caja

#### Scenario: Kiosko de una sucursal

- **GIVEN** un Kiosko cuya caja es de una sucursal y un cliente de la empresa
  matriz
- **WHEN** el cliente se identifica con su cédula
- **THEN** `identify` devuelve ese contacto, que la factura de la sucursal
  acepta

### Requirement: El cliente nuevo del Kiosko se crea en la empresa raíz de la caja

`identify/create` SHALL crear el `res.partner` nuevo con `company_id` = la
compañía raíz de la caja (`pos_config.company_id.root_id`), para que todas las
cajas de la empresa puedan facturarle. Si la creación la rechaza una validación
(p. ej. el control global de cédula duplicada de `l10n_ve_contact`), la ruta
SHALL responder con ese mensaje en `error` y sin contacto, en vez de un error de
servidor.

#### Scenario: Registro desde el Kiosko de una sucursal

- **GIVEN** un Kiosko de una sucursal, con el control de cédula duplicada por
  compañía, y una cédula registrada solo en otra empresa
- **WHEN** el cliente se registra en el Kiosko
- **THEN** se crea un contacto nuevo en la empresa matriz, el de la otra
  empresa no cambia y la siguiente identificación lo encuentra

#### Scenario: Control global de cédula duplicada

- **GIVEN** el control de cédula duplicada global de `l10n_ve_contact` y una
  cédula registrada solo en otra empresa
- **WHEN** el cliente intenta registrarse en el Kiosko
- **THEN** la respuesta trae `error` con el mensaje de la validación, sin
  contacto, y no se crea un duplicado
