# Spec delta: branch-fiscal-propagation

## ADDED Requirements

### Requirement: Las sucursales heredan los datos fiscales del contacto de su compañía raíz

El sistema SHALL mantener iguales, en el contacto de cada sucursal y en el
de su compañía raíz, los campos `type_person_id`, `withholding_type_id` y
`taxpayer_type`:

- Al escribir cualquiera de esos campos en el contacto de una compañía
  raíz, el sistema SHALL escribir el mismo valor en los contactos de todas
  sus sucursales (descendientes, activas o archivadas).
- Al crear una sucursal, el sistema SHALL aplicar a su contacto los valores
  del contacto de la raíz.
- El sistema SHALL bloquear con `ValidationError` (vía `@api.constrains`)
  cualquier escritura que deje en el contacto de una sucursal un valor
  distinto al de su raíz, indicando que se edite en la compañía raíz.

#### Scenario: Cambiar el tipo de persona en la matriz lo propaga

- **GIVEN** una compañía raíz con dos niveles de sucursales
- **WHEN** se cambia `type_person_id` en el contacto de la raíz
- **THEN** los contactos de las sucursales de ambos niveles tienen el mismo
  `type_person_id`

#### Scenario: Editar el tipo de persona de una sucursal está bloqueado

- **GIVEN** una sucursal cuyo contacto tiene los valores de su raíz
- **WHEN** se escribe un `type_person_id` distinto en el contacto de la
  sucursal
- **THEN** se lanza `ValidationError`
- **AND** el cambio no se persiste

#### Scenario: Una sucursal nueva nace con los valores de la raíz

- **GIVEN** una compañía raíz con `type_person_id`, `withholding_type_id` y
  `taxpayer_type` configurados
- **WHEN** se crea una sucursal con esa raíz como padre
- **THEN** el contacto de la sucursal tiene los tres valores de la raíz

### Requirement: La migración iguala las sucursales a su raíz

La migración 19.0.2.2.9 SHALL escribir en los contactos de las sucursales
existentes los valores del contacto de su raíz, sobrescribiendo los que
tuvieran, solo para los campos que tienen valor en la raíz. Un campo vacío
en la raíz NO SHALL tocarse en ninguna sucursal, para no borrar valores
configurados a mano. El sistema SHALL registrar un `warning` por cada valor
de sucursal que se sobrescriba con uno distinto y por cada sucursal que
conserve un valor no vacío porque la raíz tiene ese campo vacío (con el
campo, el valor y la raíz, indicando que debe configurarse la matriz).

Con los campos vacíos en la raíz la sucursal queda distinta a su raíz a
propósito: la constraint rechazará después las escrituras de ese campo en
la sucursal hasta que se configure el contacto de la matriz, y su mensaje
indica dónde hacerlo.

#### Scenario: Raíz con valor y sucursal con otro valor

- **GIVEN** una raíz con `type_person_id` configurado y una sucursal con
  otro `type_person_id`
- **WHEN** se ejecuta la migración
- **THEN** la sucursal queda con el `type_person_id` de la raíz
- **AND** se registra un `warning` con la sucursal y el campo

#### Scenario: Raíz sin tipo de persona y sucursal con tipo de persona

- **GIVEN** una raíz con `type_person_id` vacío y una sucursal con
  `type_person_id` configurado
- **WHEN** se ejecuta la migración
- **THEN** la sucursal conserva su `type_person_id`
- **AND** se registra un `warning` con la sucursal, el campo, el valor y la
  raíz que debe configurarse
- **AND** los demás campos con valor en la raíz sí se propagan a la sucursal

### Requirement: La retención ISLR de cliente de una sucursal calcula con los datos de la raíz

El sistema SHALL calcular la línea de una retención ISLR de cliente con la
sucursal como empresa activa igual que con la compañía raíz, porque el
tipo de persona de la sucursal es el de su raíz.

#### Scenario: Tipo de persona de la línea con la sucursal activa

- **GIVEN** una raíz con `type_person_id` configurado y su sucursal
- **WHEN** se evalúa `_get_islr_type_person_id()` de una línea ISLR de
  cliente con la sucursal como `company_id`
- **THEN** devuelve el `type_person_id` de la raíz
