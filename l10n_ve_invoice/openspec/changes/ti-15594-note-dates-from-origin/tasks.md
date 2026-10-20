## 1. Implementación

- [x] 1.1 `_prepare_default_values`: fecha del documento del wizard, tasa del origen.
- [x] 1.2 `default_get` y `create_debit` con validación de un solo documento.
- [x] 1.3 `create_debit` valida la fecha con `account.move._l10n_ve_check_note_date`.
- [x] 1.4 Guard de `action_post`: la nota no puede quedar antes de su origen.
- [x] 1.5 Bump de manifest `19.0.1.0.23` -> `19.0.1.0.24`.
- [x] 1.6 Exención del guard de fecha futura solo para notas automáticas (diferencial e IGTF) mediante `_l10n_ve_allows_future_date`.
- [x] 1.7 Traducciones `es_VE`.

## 2. Tests

- [x] 2.1 `tests/test_note_dates_from_origin.py` (fecha por defecto hoy, rango origen..hoy, tasa del origen, una sola factura, `action_post`).
- [x] 2.2 Tests de la exención en `l10n_ve_exchange_difference` y `l10n_ve_igtf_note_debit`.

## 3. Verificación manual

- [ ] 3.1 Reproducir los pasos del ticket (ND con fecha un día anterior a la factura): el wizard rechaza la fecha; con fecha entre la factura y hoy, la nota queda con esa fecha y la tasa de la factura.
