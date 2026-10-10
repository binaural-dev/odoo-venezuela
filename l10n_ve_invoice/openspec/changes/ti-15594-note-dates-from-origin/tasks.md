## 1. Implementación

- [x] 1.1 `_prepare_default_values` con fechas del origen en `account_debit_note.py`.
- [x] 1.2 `default_get` y `create_debit` con validación de un solo documento.
- [x] 1.3 Vista: `date` readonly en `views/account_debit_note_view.xml`.
- [x] 1.4 Bump de manifest `19.0.1.0.23` -> `19.0.1.0.24`.
- [x] 1.6 Contexto `l10n_ve_note_date` para fechar la ND de IGTF con la fecha del pago.
- [x] 1.5 Traducción `es_VE` del mensaje de un solo documento.

## 2. Tests

- [x] 2.1 `tests/test_note_dates_from_origin.py` (ND ignora fecha del wizard, rechaza varias facturas).

- [x] 2.2 `test_debit_note_takes_payment_date_not_invoice_date` en `l10n_ve_igtf_note_debit`.

## 3. Verificación manual

- [ ] 3.1 Reproducir los pasos del ticket (ND con fecha un día anterior): la nota queda con las fechas de la factura.
- [x] 3.2 Confirmar que IGTF note debit sigue creando su ND (con la fecha del pago, no la del origen): verificado con los tests de `l10n_ve_igtf_note_debit`; los 6 fallos de `TestIgtfNoteDebitUnit` son preexistentes (fallan igual en `maintenance-19.0`).
