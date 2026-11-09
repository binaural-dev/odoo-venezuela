## 1. l10n_ve_accountant — el reverso hereda la fecha de tasa del original

- [x] 1.1 Extraer `_foreign_rate_date_for_move(move)` que sigue la cadena de `reversed_entry_id` recursivamente
- [x] 1.2 `_get_foreign_rate_date()` delega en el helper; si el asiento es un reverso, valora a la fecha de tasa del asiento original (invoice_date si es factura, date si no)
- [x] 1.3 Test unitario `tests/test_reversal_foreign_rate.py`: pago en Día 1 (tasa 40) y reverso en Día 2 (tasa 50) → el reverso hereda la tasa del Día 1 ($5, no $4); más caso mismo-día sin regresión

## 2. Verificación

- [ ] 2.1 Correr `test_reversal_foreign_rate` (tag `l10n_ve_accountant_reversal_rate`) tras el upgrade del módulo
- [ ] 2.2 Navegador: factura + pago en Día 1 (tasa A); reversar el asiento del pago en Día 2 (tasa B) → el débito/crédito alterno del reverso cuadra EXACTO contra el del pago original (no usa la tasa del Día 2)
- [ ] 2.3 Repetir con pago de una factura de PdV → mismo resultado
- [ ] 2.4 Regresión NC/ND: su importe alterno sigue heredando la tasa del documento original (sin cambios)
- [ ] 2.5 Regresión pago normal (no reverso): el importe alterno se calcula a la fecha del propio asiento, sin cambios
