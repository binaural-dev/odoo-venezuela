# Tasks: `l10n_ve_accountant` — Fix `action_post()` batch-posting crash

| # | Task | Archivo | EARS |
|---|------|---------|------|
| 1 | Test RED: confirmar el crash `ValueError: Expected singleton` al postear un lote de 2+ facturas | `tests/test_account_move_post_batch.py` (nuevo) | E2 |
| 2 | Test sanity: confirmar comportamiento sin cambios para un solo registro | `tests/test_account_move_post_batch.py` | E1 |
| 3 | Fix: `self.id` → `move.id` en el `return` del wizard dentro de `action_post()` | `models/account_move.py:907` | U1, E2, E3 |
| 4 | Actualizar el test RED a GREEN: sin excepción, `default_move_id` referencia el primer move, ninguna factura queda posteada | `tests/test_account_move_post_batch.py` | E2, E3 |
| 5 | Registrar el nuevo archivo de test en `tests/__init__.py` | `tests/__init__.py` | — |
| 6 | Regresión completa de `l10n_ve_accountant` en base fresca (sin contaminación de estado de sesiones previas) | — | Gate 4/5 |
| 7 | Regresión cruzada de `country_sale_subscription`/`country_sale_subscription_fees`/`country_basic_payments` (cada uno en su configuración real de dependencias) | — | Gate 4/5 |
| 8 | QC report con evidencia completa | `specs/qc-report.md` | Gate 5 |

## Trazabilidad

| ID | Tasks |
|---|---|
| U1 | 3 |
| E1 | 2, 4 |
| E2 | 1, 3, 4 |
| E3 | 3, 4 |

## Validación

- [x] Todas las tasks referencian un requisito EARS del spec.
- [x] TDD real: RED confirmado antes del fix (task 1), GREEN confirmado después (task 4).
- [x] Pre-commit: sin hallazgos nuevos en los archivos modificados (issues preexistentes en otros
      archivos del módulo, no relacionados).
- [x] Regresión sin regresiones nuevas en ningún módulo de la cadena de dependencias real.
- [ ] Gate 6 (commit) — pendiente de autorización explícita del usuario.

## Addendum: Fix real — `clean_context()` en el wizard de alerta de posteo

| # | Task | Archivo | EARS |
|---|------|---------|------|
| 9 | Instrumentación temporal de diagnóstico (log + stack) en `account.move.write()` | `models/account_move.py` | — (diagnóstico, no funcional) |
| 10 | Captura del stack real en producción (`contryclub-stg-2`), confirmando la causa exacta | — | — |
| 11 | Fix: `clean_context(self.env.context)` antes de `action_post()` en `action_confirm()` | `wizard/move_action_post_alert_views.py` | U2, E4 |
| 12 | Test: contexto del wizard carga `default_move_id` (sanity check) | `tests/test_move_action_post_alert_wizard.py` | U2 |
| 13 | Test: `action_post()` ya no recibe `default_move_id` desde `action_confirm()` | `tests/test_move_action_post_alert_wizard.py` | U2 |
| 14 | Test: reproducción directa (contexto sucio → `UserError`; contexto limpio → pago con asiento propio) | `tests/test_move_action_post_alert_wizard.py` | E4 |
| 15 | Registrar el nuevo archivo de test en `tests/__init__.py` | `tests/__init__.py` | — |
| 16 | Regresión completa en BD fresca | — | Gate 4/5 |
| 17 | QC report (addendum) | `specs/qc-report.md` | Gate 5 |

### Trazabilidad Addendum

| ID | Tasks |
|---|---|
| U2 | 11, 12, 13 |
| E4 | 11, 14 |

### Validación

- [x] Instrumentación de diagnóstico capturó el stack real en producción (no se adivinó la causa).
- [x] Fix aplicado (`clean_context`), reproducido y confirmado con test dedicado.
- [x] Regresión completa: 178/178 tests, 0 fallos, 0 errores (BD fresca).
- [ ] Gate 6 (commit) — pendiente de autorización explícita del usuario.
