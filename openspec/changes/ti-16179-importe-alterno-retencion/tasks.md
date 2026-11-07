## 1. l10n_ve_payment_extension — importe alterno con la fecha de tasa del asiento

- [x] 1.1 `account.payment._get_retention_foreign_rate_date()` como fuente única de la fecha de tasa de una retención
- [x] 1.2 `account.move.line._get_foreign_rate_date` delega en ese helper
- [x] 1.3 `_compute_foreign_amount` usa esa fecha en pagos de retención (depends: `is_retention`, `retention_line_ids.move_id`)
- [x] 1.4 Pruebas con `Form` por tipo de retención (IVA, ISLR, municipal) y de documento (factura, NC, ND; cliente y proveedor), con la tasa subiendo, bajando e igual (tag `retention_payment_foreign_amount_rate_date`)
- [x] 1.5 Pruebas con `Form` de pagos normales (formulario del pago de cliente y proveedor, y asistente "Registrar pago") y comparación retención vs pago normal: el importe mostrado de cada uno cuadra con su propio asiento

## 2. Verificación

- [ ] 2.1 Correr `retention_payment_foreign_amount_rate_date` tras el upgrade del módulo
- [ ] 2.2 Navegador: retención sobre una factura de días atrás con tasa distinta → el importe alterno del pago coincide con el de las líneas del asiento
- [ ] 2.3 Regresión: un pago que no es retención calcula su importe alterno a la fecha del propio pago
