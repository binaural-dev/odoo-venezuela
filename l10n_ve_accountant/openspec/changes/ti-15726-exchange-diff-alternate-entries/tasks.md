## 1. Implementación

- [x] 1.1 Escenario 1: ND/NC sin montos alternos (`l10n_ve_exchange_difference`). Sin migración: las notas ya emitidas se corrigen a mano si se reportan.
- [x] 1.2 Escenario 2: `open_reconcile_view` recorre toda la cadena de liquidación.
- [x] 1.3 Escenario 3: visibilidad del check "Pago indexado" y rechazo de importe 0.0.
- [x] 1.4 Escenario 4: `l10n_ve_use_foreign_exchange_diff` por defecto `True`; constraint omitido al crear/cargar plan; revalidación al terminar `_load`.
- [x] 1.5 Escenario 5: `foreign_balance` recalculado tras redistribuir el residuo. Sin migración (fix hacia adelante).
- [x] 1.6 Extra: bloqueo de volver a borrador (asiento alterno y ND/NC de diferencial).
- [x] 1.7 Traducciones `es_VE` y bump de versión (`19.0.1.0.32`).

## 2. Tests

- [x] 2.1 `l10n_ve_accountant/tests/test_foreign_exchange_diff.py` (default, constraint, chart load, borrador, wizard).
- [x] 2.2 `l10n_ve_accountant/tests/test_foreign_balance.py` (saldo alineado, importe 0.0).
- [x] 2.3 `l10n_ve_exchange_difference/tests/test_exchange_note_foreign_and_draft.py`.
- [x] 2.4 `l10n_ve_igtf`: tests con el diferencial alterno encendido.

## 3. Verificación manual

- [ ] 3.1 Staging: factura nueva con redistribución de residuo, débito alterno = saldo alterno.
- [ ] 3.2 Funcional: ND históricas de períodos cerrados y "Total alterno" / `foreign_untaxed_total` de la ND.
