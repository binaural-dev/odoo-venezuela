# Spec delta: invoice-layout-line-exclusions

## ADDED Requirements

### Requirement: Los guards de línea de producto excluyen toda la familia de maquetado

Todo guard de `l10n_ve_invoice` que valide propiedades exigibles a una línea
de **producto** SHALL excluir las líneas con `display_type` en
`('line_section', 'line_subsection', 'line_note')`, y SHALL NOT exigirles
precio distinto de cero, impuesto asignado ni `product_id`.

Motivo: una línea de maquetado es un encabezado o una nota visual. No tiene
precio (`price_unit = 0` por definición), no puede llevar impuesto y no
representa nada acreditable. `line_subsection` es el `display_type` que Odoo
19 agregó a esta familia; quedó fuera de las tres tuplas del módulo y eso
hizo infacturable cualquier documento que usara una subsección.

Los tres guards afectados son `_check_price_in_zero`,
`_check_refund_against_origin` y `action_post`. SHALL mantenerse en sincronía:
son el mismo concepto expresado tres veces, y el defecto original fue
actualizar ninguna de las tres.

#### Scenario: Crear una factura con una subsección

- **GIVEN** una factura de cliente con una línea `line_section`, una
  `line_subsection`, una `line_note` y una línea de producto con precio e
  impuesto válidos
- **WHEN** se crea la factura
- **THEN** la creación tiene éxito
- **AND** no se lanza `"An invoice cannot have a line with a price of zero"`

#### Scenario: Validar una factura con una subsección

- **GIVEN** la factura del escenario anterior, en estado borrador
- **WHEN** se ejecuta `action_post()`
- **THEN** la factura queda en estado `posted`
- **AND** no se lanza `"Add a tax to each product line..."` por la
  subsección, que no puede llevar impuesto

#### Scenario: Nota de crédito con una subsección

- **GIVEN** una nota de crédito contra una factura de origen, con una línea
  `line_subsection` intercalada entre sus líneas de producto
- **WHEN** se valida la correspondencia con el documento de origen
- **THEN** la subsección no se cuenta como producto a acreditar
- **AND** no se le exige `product_id` ni presencia en la factura de origen

#### Scenario: Una línea de producto a precio cero sigue bloqueada

- **GIVEN** una factura con una línea de `display_type = 'product'` y
  `price_unit = 0`, que no es una línea de descuento reconocida
  (`_get_discount_lines`)
- **WHEN** se crea la factura fuera del punto de venta y fuera de un flujo de
  lealtad
- **THEN** se lanza `ValidationError`
- **AND** el guard conserva el comportamiento que tenía antes del fix

#### Scenario: Una línea de producto sin impuesto sigue bloqueada

- **GIVEN** una factura con una línea de producto sin `tax_ids`
- **WHEN** se ejecuta `action_post()`
- **THEN** se lanza `ValidationError` exigiendo el impuesto
- **AND** el guard conserva el comportamiento que tenía antes del fix
