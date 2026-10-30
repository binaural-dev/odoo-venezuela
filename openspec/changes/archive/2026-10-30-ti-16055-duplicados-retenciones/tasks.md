## 1. l10n_ve_payment_extension

- [x] 1.1 `action_view_retention`: configuración por tipo con vistas explícitas; tipo desconocido sin acción
- [x] 1.2 Spec: escenario de diferenciador vacío y requisito de los botones de retenciones

## 2. Tests

- [x] 2.1 `test_retention_consolidated_duplicates.py`: diferenciador vacío en ambos sentidos para IVA, ISLR y municipal, y vacío contra vacío bloquea
- [x] 2.2 `test_wizard_payment_batch.py`: comprueba el id de vista real; caso de tipo desconocido

## 3. Verificación

- [x] 3.1 BD nueva `--without-demo=all`, contenedor `proj`: `-i l10n_ve_payment_extension --test-tags /l10n_ve_payment_extension:TestRetentionConsolidatedDuplicates,/l10n_ve_payment_extension:TestAccountMoveRemaining`: 27 tests, 0 fallos
