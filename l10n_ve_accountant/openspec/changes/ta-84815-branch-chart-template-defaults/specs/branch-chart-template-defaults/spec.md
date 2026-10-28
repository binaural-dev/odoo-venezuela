# branch-chart-template-defaults

### REQ-BCT-001: Defaults de cuenta de una sucursal
Al cargar la plantilla contable sobre una sucursal, si el xmlid de la plantilla para un default de propiedad de cuenta no existe
para la compañía matriz, la sucursal SHALL tomar el valor por defecto que la matriz ya tiene para ese campo.

#### Scenario: Matriz con plan propio
- **GIVEN** una matriz con `chart_template` definido, sin xmlids de cuentas de la plantilla y con defaults de cuenta por cobrar y por pagar
- **WHEN** se crea una sucursal de esa matriz
- **THEN** la sucursal se crea y sus defaults de cuenta por cobrar y por pagar son los de la matriz

#### Scenario: Xmlid existente
- **GIVEN** una matriz con el xmlid de la plantilla para un default
- **WHEN** se crea una sucursal
- **THEN** el core resuelve ese default; el respaldo no interviene

### REQ-BCT-002: Matriz sin default de por cobrar o por pagar
Si el xmlid no existe y no hay valor por defecto (ni de la matriz ni global) para la cuenta por cobrar o por pagar de `res.partner`, la
creación de la sucursal MUST fallar con **un solo** `UserError` que nombre la matriz y liste todas las propiedades faltantes con su xmlid.
No se escribe ningún default de la sucursal cuando falla.

### REQ-BCT-003: Compañías sin padre
La carga de la plantilla sobre una compañía sin padre MUST NOT cambiar.

### REQ-BCT-004: Default global
Si el xmlid no existe y el default del campo es global (sin compañía), el sistema SHALL NOT copiarlo ni fallar: la sucursal ya lo recibe.

#### Scenario: Matriz migrada con default global
- **GIVEN** una matriz sin xmlids de plantilla y con el default de cuenta por cobrar definido para todas las compañías
- **WHEN** se crea una sucursal
- **THEN** la sucursal se crea y no se escribe ningún default propio para ese campo

### REQ-BCT-005: Campos de la compañía
Las propiedades de `res.company` de la plantilla (p. ej. `downpayment_account_id`) MUST NOT ser tratadas por este respaldo; las resuelve el core.

### REQ-BCT-006: Sucursales de varios niveles
Los valores copiados SHALL provenir de la compañía raíz, no de una sucursal intermedia.

### REQ-BCT-007: Propiedades no obligatorias
Si el xmlid no existe y no hay default que heredar para una propiedad distinta de la cuenta por cobrar y por pagar, el sistema SHALL
dejar un `warning` y crear la sucursal sin ese default.

#### Scenario: Propiedad no obligatoria sin default
- **GIVEN** una matriz con defaults de por cobrar y por pagar, y una propiedad adicional de la plantilla sin xmlid ni default
- **WHEN** se crea una sucursal
- **THEN** la sucursal se crea, hereda por cobrar y por pagar, y se registra un `warning` por la propiedad faltante

### REQ-BCT-008: Matriz sin `chart_template`
Una sucursal de una matriz sin `chart_template` MUST NOT verse afectada: el core no carga la plantilla en la sucursal y no se escribe
ningún default ni log de este respaldo.

#### Scenario: Matriz sin plantilla
- **GIVEN** una matriz sin `chart_template`
- **WHEN** se crea una sucursal y se confirma la transacción
- **THEN** la sucursal se crea sin `chart_template`, sin defaults propios y sin avisos de este módulo

