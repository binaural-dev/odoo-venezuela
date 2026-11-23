## 1. l10n_ve_igtf — avisos de pendientes por condición

- [x] 1.1 `views/account_move.xml`: los cuatro reemplazos ubican el aviso por `invoice_has_outstanding` y el `move_type` de su `invisible` (corrige el `[3]` repetido)
- [x] 1.2 `tests/test_move_form_outstanding_alerts.py`: un aviso IGTF por tipo, con y sin un `alert-info` agregado antes que IGTF
- [x] 1.3 `__manifest__.py`: versión 19.0.1.2.23

## 2. l10n_ve_igtf_note_debit — anclaje del aviso de notas de débito

- [x] 2.1 `views/account_move_views.xml`: aviso anclado después del aviso de pendientes de `in_refund`
- [x] 2.2 `__manifest__.py`: versión 19.0.1.0.3

## 3. Verificación

- [x] 3.1 La prueba nueva falla con las vistas anteriores al cambio
- [x] 3.2 Actualizar `l10n_ve_igtf` y `l10n_ve_igtf_note_debit` con `binaural_purchase` y `l10n_ve_sale` instalados y correr `/l10n_ve_igtf`, `/l10n_ve_igtf_note_debit`
- [ ] 3.3 Revisar en el formulario: factura y nota de crédito de proveedor y de cliente con pendientes, y factura desde una orden de compra y de venta con aviso de tasa
