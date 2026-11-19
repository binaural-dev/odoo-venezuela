## 1. l10n_ve_accountant — Detalle de ventas con varias monedas

- [x] 1.1 `_compute_detailed_amounts`: formatear con `record.currency_id`; impuestos desde `tax_amount_currency`; `gross_discount_amount` = bruto − descuento
- [x] 1.2 Reporte: claves de Odoo 19 (`total_amount_currency`, `formatted_total_amount_currency`) y pagos con `state in (in_process, paid)`
- [x] 1.3 Facturas y pagos agrupados por moneda con subtotal en esa moneda; total general de ventas y de pagos en la moneda de la compañía
- [x] 1.4 Pruebas `TestInvoiceDetailsReport` (8 casos nuevos, 7 fallan contra el código original)
- [x] 1.5 Versión del manifest 19.0.1.0.45

## 2. Verificación

- [x] 2.1 Lote VEF + USD: el campo se calcula sin `Expected singleton` y cada factura se formatea con su moneda
- [x] 2.2 Con 2 facturas VEF y 2 USD (IVA 16%, descuento) los subtotales por moneda y el total general en VEF cuadran
- [x] 2.3 Pagos VEF y USD: subtotal por moneda y total general en VEF
- [x] 2.4 `TestAccountMoveCore`, `TestCoverageGaps` y `TestAlternateTotalsBlock`: sin regresiones (81 pruebas, 0 fallos)
- [ ] 2.5 Validación con los documentos reales de Ganchos Venezolanos en staging: la hace funcional en el ticket
