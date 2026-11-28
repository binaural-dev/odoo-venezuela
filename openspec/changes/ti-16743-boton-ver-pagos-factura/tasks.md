## 1. l10n_ve_igtf — botón Ver en el popover de pagos

- [x] 1.1 `models/account_move.py`: el override llama a `super()` y conserva el filtro de facturas publicadas; se quita la copia del diccionario
- [x] 1.2 `tests/test_igtf_payments_widget_open_move.py`: `can_open_move` presente y verdadero; sin widget en borrador
- [x] 1.3 Versión 19.0.1.2.25 en `__manifest__.py`

## 2. Verificación

- [x] 2.1 Staging: `odoo-update l10n_ve_igtf` sin errores; la factura publicada trae `can_open_move: true` e `is_retention`; las facturas en borrador no traen widget
- [ ] 2.2 Suite de `l10n_ve_igtf` en base limpia
