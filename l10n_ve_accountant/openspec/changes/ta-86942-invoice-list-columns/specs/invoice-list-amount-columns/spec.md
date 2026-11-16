# Spec delta: invoice-list-amount-columns

## ADDED Requirements

### Requirement: Las listas de facturas y notas agrupan y totalizan los montos

Las listas de facturas y notas de crédito de clientes y de proveedores
(`account.view_out_invoice_tree`, `account.view_out_credit_note_tree`,
`account.view_in_invoice_bill_tree`, `account.view_in_invoice_refund_tree`) SHALL
mostrar, de forma contigua y en este orden, `amount_untaxed_signed`,
`amount_total_signed`, `foreign_untaxed_total` y `foreign_total_billed`.

Cada una de esas columnas SHALL llevar `sum` (totaliza al pie), SHALL ser
visible por defecto y SHALL tener un `width` predeterminado.

Motivo: las columnas intercalaban monedas, no todas totalizaban y los números
largos se cortaban hasta que cada usuario ajustaba el ancho.

#### Scenario: Orden de columnas

- **GIVEN** cualquiera de las cuatro listas
- **WHEN** se carga la vista
- **THEN** las cuatro columnas de montos son contiguas
- **AND** van Bs. sin impuestos, Bs. total, $ sin impuestos y $ total

#### Scenario: Totales al pie

- **GIVEN** una lista con varias facturas
- **WHEN** se muestra la lista
- **THEN** cada una de las cuatro columnas muestra su total al pie

#### Scenario: Ancho predeterminado

- **GIVEN** un usuario que entra por primera vez a la lista
- **WHEN** se muestra la lista
- **THEN** las columnas de montos tienen 180px y no se cortan con puntos
  suspensivos
