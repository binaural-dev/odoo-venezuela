# Tasks

## 0. Preparación

- [x] 0.1 Hallazgo del code review del ticket 16351 (2026-11-12): el Kiosko lee `res.currency` sin pasar por
      `_load_pos_data_read`

## 1. Implementación

- [x] 1.1 `models/res_currency.py`: `_load_pos_self_data_read` con `_apply_pos_session_rates`
- [x] 1.2 Versión 19.0.1.8.0

## 2. Pruebas

- [x] 2.1 `tests/test_kiosk_session_rate.py`: Kiosko sin tasa no abre; monedas con la tasa del día de la sesión
      (`--test-tags /l10n_ve_pos_self_order:TestKioskSessionRate`: 2 en verde; sin el override falla el segundo)
- [x] 2.2 Suite completa del módulo en base nueva con `l10n_ve_pos` (105, sin fallos)

## 3. Cierre

- [x] 3.1 Archivar el change
