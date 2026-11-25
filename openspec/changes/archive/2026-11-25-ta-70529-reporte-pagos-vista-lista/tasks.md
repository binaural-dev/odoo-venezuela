## 1. l10n_ve_pos — vista del Reporte de pagos

- [x] 1.1 `wizard/payment_report.xml`: `pos_config_ids` con `mode="list"`
- [x] 1.2 `tests/test_pos_payment_report_view.py`: el formulario abre sin `mode="tree"`
- [x] 1.3 Versión del manifest a `19.0.1.28.2`

## 2. Verificación

- [x] 2.1 La prueba nueva falla sin el cambio (1 error) y pasa con él
- [x] 2.2 `l10n_ve_pos` actualiza sin errores en una base existente
- [ ] 2.3 Abrir el menú *Punto de venta > Reportes > Reporte de pagos* en el ambiente de validación y generar el reporte
