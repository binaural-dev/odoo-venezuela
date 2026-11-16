# Tasks

## 1. Diagnóstico

- [x] 1.1 Ubicada la vista: `account.view_out_invoice_tree` hereda de
      `account.view_invoice_tree`; las columnas propias las agrega
      `l10n_ve_accountant_view_invoice_tree_inherit`
- [x] 1.2 Confirmado que las listas de notas de crédito y de proveedores
      heredan de la misma vista, por lo que el cambio las cubre

## 2. Vista

- [x] 2.1 Agrupar columnas: Bs. (sin impuestos, total) y luego $ (sin
      impuestos, total)
- [x] 2.2 Mover `amount_tax_signed` justo después del total sin impuestos (Bs.)
- [x] 2.3 `sum="Total"` y `optional="show"` en las cuatro columnas propias
- [x] 2.4 `width="180px"` solo en columnas de montos (`Número` queda con el ancho nativo)
- [x] 2.5 Bump de manifest `19.0.1.0.44` → `19.0.1.0.45`

## 3. Tests

- [x] 3.1 `tests/test_invoice_list_columns.py` (2 pruebas): orden contiguo
      Bs./$ (con el impuesto tras el sin impuestos en Bs.) y presencia de `sum` y
      `width` en las cuatro listas
- [x] 3.2 Verificado en una base limpia (0 fallos de 2)
- [x] 3.3 Verificación visual en las cuatro listas con facturas de prueba
