## 1. l10n_ve_pos — alterno del vuelto en el asiento

- [x] 1.1 Helper `pos.order._amount_to_foreign(amount)` (monto Bs. × `foreign_currency_rate`, redondeado a la moneda foránea)
- [x] 1.2 Override de `pos.order._process_payment_lines` que, tras `super()`, rellena `foreign_amount` y `foreign_rate` de las líneas `is_change` sin alterno
- [x] 1.3 Fallback en `pos.payment._create_payment_moves`: derivar el alterno de la tasa de la orden cuando `foreign_amount == 0`
- [x] 1.4 Bump de manifest `l10n_ve_pos` 1.12 → 1.13

## 2. Verificación

- [x] 2.1 Probar en navegador: venta con pago > total sin método de vuelto → el asiento del vuelto (pago de factura) muestra Débito/Crédito alterno con el monto en USD (no 0,00). Verificado: orden C4-CCS - 000001, asiento del vuelto PVCC4/2026/0008 con foreign_debit/foreign_credit $0,69 (antes $0,00)
- [x] 2.2 Conciliación en USD: pago alterno − vuelto alterno = alterno de la factura (cuadra). Verificado: pago $5,19 − vuelto $0,69 = $4,50 = factura FCCS4 00049155
- [ ] 2.3 Regresión: venta pagada justa (sin vuelto) sigue con su alterno correcto
- [ ] 2.4 Reproducir la variante pagando en USD (EFE $) por encima del total, para confirmar el síntoma de la factura del ticket
- [ ] 2.5 Cierre de sesión de una orden NO facturada con vuelto → asiento cruzado con alterno correcto
