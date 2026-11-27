## MODIFIED Requirements

### Requirement: Unicidad del nombre del asiento por partner, compañía y diario

El sistema DEBE (MUST) declarar en `account.move` el índice único `account_move_unique_name` (`_unique_name`) sobre (`name`, `partner_id`, `company_id`, `journal_id`) para asientos publicados con nombre distinto de `/`, en reemplazo del índice del core sobre (`name`, `journal_id`). Mientras el índice de la base no sea el ampliado, antes de crearlo el sistema DEBE (MUST) buscar asientos publicados con el mismo `name`, `partner_id`, `company_id` y `journal_id` y, si existen, DEBE detener la instalación o actualización con un `UserError` que liste hasta 20 casos (proveedor, diario, número y cantidad). NO DEBE (MUST NOT) modificar ningún dato para crear el índice: los duplicados se revisan a mano. Los asientos sin `partner_id` no cuentan como duplicados entre sí.

#### Scenario: Factura de proveedor duplicada

- **WHEN** se intenta publicar un documento con el mismo `name`, mismo partner, misma compañía y mismo diario que otro ya publicado
- **THEN** la base de datos rechaza la operación por el índice único

#### Scenario: Mismo número para distintos proveedores

- **WHEN** dos proveedores tienen facturas publicadas con el mismo número en el mismo diario y compañía
- **THEN** ambas se publican y el índice se crea

#### Scenario: Duplicados históricos bloquean la instalación sin renombrar

- **GIVEN** asientos publicados con el mismo número, proveedor, diario y compañía
- **WHEN** se instala o actualiza el módulo y el índice de la base no es el ampliado
- **THEN** se lanza un `UserError` que lista los casos, ningún asiento cambia de número y el índice no se crea

#### Scenario: Índice del core reemplazado

- **GIVEN** el índice `account_move_unique_name` sobre (`name`, `journal_id`), con o sin comentario
- **WHEN** se instala o actualiza el módulo sin duplicados
- **THEN** el índice queda sobre (`name`, `partner_id`, `company_id`, `journal_id`)

#### Scenario: Base que ya tiene el índice ampliado

- **WHEN** se actualiza una base cuyo `account_move_unique_name` ya incluye `partner_id`
- **THEN** no se buscan duplicados, el índice se conserva y se borra el marcador `account_move_unique_name_ve` de la implementación anterior

#### Scenario: Asientos sin proveedor

- **WHEN** hay asientos publicados con el mismo número y diario y sin `partner_id`
- **THEN** no se consideran duplicados y el índice se crea
