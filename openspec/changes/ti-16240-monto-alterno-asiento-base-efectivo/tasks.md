## 1. l10n_ve_accountant — monto alterno en el asiento de base efectivo

- [x] 1.1 `_get_foreign_value`: las líneas `tax`/`payment_term` de asientos con `tax_cash_basis_origin_move_id` no usan el atajo de `foreign_balance`
- [x] 1.2 Pruebas con `Form` (`TestCashBasisForeign`): factura de 100 USD + 16% IVA al pagar a tasa 889,5754; asiento de la factura, del pago y del IMBEF con montos alternos en las 4 líneas; pago parcial proporcional
- [x] 1.3 Sin el arreglo fallan los dos casos del IMBEF (`0.0 != 16.0` y `0.0 != 8.0`)

## 2. Verificación

- [ ] 2.1 Cobro con retención de IVA sobre una factura con impuesto "al pagar": el IMBEF trae el monto alterno en las líneas de impuesto
- [ ] 2.2 Script para recalcular los IMBEF ya generados con el alterno en 0
- [ ] 2.3 Navegador: factura a ente público (posición fiscal Gubernamental, "16% Ventas Público"), cobrar y revisar el IMBEF
