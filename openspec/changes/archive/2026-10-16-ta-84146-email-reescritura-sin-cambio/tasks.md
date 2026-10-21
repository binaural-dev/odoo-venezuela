# Tasks: ta-84146-email-reescritura-sin-cambio

## Scope

Backport acotado del hunk `write()` de 4d9361e4 (upstream 19.0). `create()` y la re-validación por lote quedan **fuera de alcance** (tarea 84357). Límite conocido I2 (cambio de `type` a `contact` sin cambio de email no se valida) se documenta, no se modifica.

- [x] 1. Cherry-pick de 4d9361e4 de 19.0 (`--no-commit`), resolviendo el conflicto de versión del manifest a 1.9 (versión corta de maintenance) y **revertir el bloque batch de `create()`** para dejar `create()` como en `maintenance-19.0`, conservando solo el hunk `write()` (`email_changed`).
- [x] 2. Test del escenario TA 84146 (`test_portal_address_reedit_unchanged_email`): reedición de dirección portal con email sin cambio no valida duplicidad; cambio de email a uno ajeno sí lanza `ValidationError`.
- [x] 3. Test del ramo `type != contact` en el bucle de `write` (`test_write_changed_email_on_delivery_address_skips_check`).
- [x] 4. Quitar `test_duplicate_email_in_same_batch` (perteneciente al lote de `create`, fuera de alcance).
- [x] 5. Tests nuevos del alcance de `write`:
  - [x] 5a. `test_write_multi_record_only_changed_fails` (multi-record: falla por el que cambia, no por el que reescribe).
  - [x] 5b. `test_write_unchanged_email_with_child_of_any_type` (hijos `delivery`/`invoice`/`other` con email compartido: reescritura no lanza).
  - [x] 5c. `test_write_new_duplicated_email` (cambio a email ajeno lanza).
- [x] 6. Demostrar ROJO (sin el hunk `write`: `ValidationError` en reedición y en los 4 tests de escritura) y VERDE (con el fix: 13 tests, 0 failed, 0 errors, 2 skipped).
- [x] 7. Corrida completa de `l10n_ve_contact` con cobertura: `write()` (líneas 186–205 de `res_partner.py`) cubierto al 100%; cobertura total de módulo 74% (preexistente).
- [x] 8. Regresión de los 5 módulos website (`binaural_website`, `binaural_website_sale`, `binaural_website_sale_comparison`, `binaural_website_sale_transit`, `binaural_website_sale_delivery`): 447 tests, 0 failed, 0 errors, 0 skipped.
- [x] 9. Pylint-odoo mandatory (read-only) sobre los `.py` tocados: exit 0, sin mensajes.
- [x] 10. Spec delta con etiquetas EARS, Out of Scope (lote `create` = 84357) y trazabilidad requirement→task→test; actualización de `openspec/specs/l10n_ve_contact/spec.md` para reflejar **solo** el cambio de `write` (sin escenario de lote).
- [x] 11. QC report fuera del módulo en `src/.sdd/reports/ta84146/qc-report.md`; eliminar `l10n_ve_contact/specs/qc-report.md`.
- [x] 12. Archivar el cambio en `openspec/changes/archive/`.
- [ ] 13. Commit y PR (Gate 6: pendiente de humano; fuera de esta ronda).
