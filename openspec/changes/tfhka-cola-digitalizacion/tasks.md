## 1. Documentar el rediseño de cola (ya implementado en el PR #1322)

- [x] 1.1 Requirement nuevo: cola de digitalización con cron unificado (estados, invariantes,
      halt-on-error por modelo, reintento de rate-limit)
- [x] 1.2 Requirement nuevo: recuperación de digitalizaciones interrumpidas (`processing` colgado)
- [x] 1.3 Requirement nuevo: estado `not_applicable` en facturas fuera de alcance
- [x] 1.4 Requirement nuevo: banner de alerta de documentos bloqueados para usuarios internos
- [x] 1.5 Reescribir "Emisión digital de facturas, notas de débito y notas de crédito" para
      describir encolar-al-postear en vez de emitir inline
- [x] 1.6 Reescribir "Emisión digital de comprobantes de retención IVA e ISLR" (idem)
- [x] 1.7 Reescribir "Digitalización automática de guías de despacho" (idem)
- [x] 1.8 Eliminar el requirement "Bloqueo de publicación con documentos sin digitalizar del mismo
      diario" (guard retirado, la cola cubre la misma garantía)

## 2. Bug fix: retención marcada `success` sin emitir (mismatch de secuencia)

- [x] 2.1 `TfhkaSequenceMismatchError` en `tfhka_service_base.py` (hereda `TfhkaDataError`)
- [x] 2.2 Extraer `_tfhka_check_retention_sequence_gap` en `tfhka_retention_service.py`
- [x] 2.3 `send_retention()` lanza `TfhkaSequenceMismatchError` en vez de retornar la acción del
      wizard
- [x] 2.4 Botón `action_tfhka_review_sequence_mismatch()` en `account.retention`, visible en
      `data_error`
- [x] 2.5 Vistas: botón nuevo en `account_retention_iva.xml` y `account_retention_islr.xml`
- [x] 2.6 Actualizar el requirement "Alerta confirmable de secuencia en retenciones" con el
      comportamiento corregido
- [x] 2.7 Tests: reintento manual con secuencia desfasada termina en `data_error` (no `success`, no
      `is_digitalized`); confirmar el wizard reencola y el siguiente tick del cron sí digitaliza

## 3. Verificación

- [ ] 3.1 `./odoo test the_factory_19 l10n_ve_invoice_digital,binaural_third_party_invoice_digital,l10n_ve_dispatch_guide_digital`
- [ ] 3.2 `./scripts/precommit` sobre los archivos tocados
- [x] 3.3 Archivar este change contra `openspec/specs/l10n_ve_invoice_digital/spec.md`
