## 1. l10n_ve_pos — precio foráneo de las líneas de reembolso

- [x] 1.1 Override de `pos.order.line.create` que, tras `super()`, repone `foreign_price` en las líneas con `refunded_orderline_id` y sin precio foráneo, tomándolo de la línea original
- [x] 1.2 Red de seguridad en `pos.order._get_invoice_lines_values`: si la línea de PdV es de reembolso y llega sin `foreign_price`, usar el de la línea original
- [x] 1.3 Bump de manifest `l10n_ve_pos` 1.12 → 1.13
- [x] 1.4 Unit tests (`tests/test_pos_refund_foreign_price.py`): backfill desde la original, no sobrescribir un valor presente, no tocar líneas de venta normales, no reponer si la original tampoco tiene alterno

## 2. Verificación

- [ ] 2.1 Probar en navegador: vender + facturar en el día 1 (tasa R1); cambiar la tasa (día 2, R2); reembolsar la orden desde el PdV. En Contabilidad → Apuntes contables, la NC muestra Débito alterno (USD) en las líneas de producto (no 0,00)
- [ ] 2.2 Reversión 1:1: el saldo en USD de la NC cuadra contra la factura de origen (mismo monto alterno por línea de producto, a la tasa del día 1, no del día 2)
- [ ] 2.3 IVA y cuenta por cobrar de la NC con alterno correcto y el asiento balanceado en USD
- [ ] 2.4 Reembolso parcial (una de varias líneas / cantidad parcial) → alterno correcto en la línea reembolsada
- [ ] 2.5 Regresión: una venta normal facturada mantiene su alterno correcto (sin cambios)
