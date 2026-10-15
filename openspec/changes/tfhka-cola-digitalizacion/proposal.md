## Why

`l10n_ve_invoice_digital` emitía cada documento (factura, retención, guía de despacho) de forma
síncrona, inline, en el mismo request que lo confirmaba o publicaba: si TFHKA rechazaba la llamada
o tardaba, la excepción podía revertir la propia confirmación/posteo del documento, y no había
buena respuesta para el rate-limit de TFHKA bajo volumen alto (ticket 15207: al confirmar ambas
facturas de una factura a terceros, la digitalización de la segunda podía fallar o bloquear la
primera). El PR #1322 (odoo-venezuela) reemplaza esa emisión síncrona por una **cola con cron**
(`tfhka.digitalization.mixin`, compartida por `account.move`, `account.retention` y
`stock.picking`): confirmar/publicar un documento solo lo encola (un `write` de campo, nunca una
llamada HTTP, así que nunca puede revertir el posteo), y un cron unificado
(`_tfhka_cron_process_queue_multi`) es el único emisor real, avanzando la cola de cada modelo un
documento a la vez. Esto habilita además que `binaural_third_party_invoice_digital` (PR #2801,
integra-addons) encole también la factura hija de una factura a terceros al confirmarse la
principal, sin la carrera que motivó el ticket.

Este documento describe ese rediseño (openspec/specs/l10n_ve_invoice_digital/spec.md seguía
describiendo el flujo síncrono anterior) y corrige, de paso, un bug real detectado en el review del
PR: el mecanismo de confirmación de secuencia desincronizada en retenciones
(`account.retention.alert.wizard`) asumía un humano presente para contestarlo en el acto; con el
cron como único emisor, ese wizard nunca se abre, y `send_retention()` devolvía la acción del
wizard sin lanzar excepción -- el mixin, que solo mira excepciones, marcaba la retención
`success`/`is_digitalized=True` sin haberla enviado a TFHKA.

## What Changes

- **Cola de digitalización**: nuevo modelo abstracto `tfhka.digitalization.mixin` con estados
  `none/queued/processing/success/error/data_error/not_applicable`, cron unificado que intercala
  documentos por modelo, recuperación de intentos `processing` interrumpidos por un crash
  (`_tfhka_recover_stuck_processing`, replay desde `tfhka.api.log` o `error` tras un período de
  gracia), y un banner de alertas para documentos bloqueados en `error`/`data_error`.
  Reemplaza la emisión inline previa en `account.move`, `account.retention` y `stock.picking`.
- **Bug fix (retención)**: `tfhka_retention_service.send_retention()` ahora lanza
  `TfhkaSequenceMismatchError` (nueva excepción, hereda de `TfhkaDataError`) en vez de devolver la
  acción del wizard, cuando el correlativo de Odoo no coincide con el de TFHKA y nadie confirmó
  seguir de todas formas. El mixin ya clasifica cualquier `TfhkaDataError` como `data_error` sin
  cambios adicionales. Se agrega el botón manual
  `account.retention.action_tfhka_review_sequence_mismatch()`, visible en `data_error`, que
  recalcula la brecha (solo lectura) y abre el mismo wizard -- su `action_confirm()` no cambia.
- **Guard de posteo eliminado**: el bloqueo de publicación por "factura anterior del mismo diario
  sin digitalizar" (`move.action.post.alert.wizard`) ya no es necesario -- la cola, al procesar en
  orden FIFO por modelo y detenerse en el primer error, hace la misma garantía sin bloquear el
  posteo del documento siguiente.

## Impact

- Specs afectadas: `l10n_ve_invoice_digital` (este documento).
- Código ya en el PR (no se toca en este change de OpenSpec, salvo el fix de 1.1): mixin
  (`models/tfhka_digitalization_mixin.py`), migraciones de backfill
  (`migrations/19.0.1.3.0/`, `19.0.1.4.0/`), cron (`data/ir_cron.xml`), vistas de estado, y el
  impacto correspondiente en `l10n_ve_dispatch_guide_digital` (guías de despacho encoladas igual).
- Código nuevo de este change: `services/tfhka_retention_service.py`
  (`_tfhka_check_retention_sequence_gap`, `send_retention` lanza en vez de retornar),
  `services/tfhka_service_base.py` (`TfhkaSequenceMismatchError`), `models/account_retention.py`
  (`action_tfhka_review_sequence_mismatch`), `views/account_retention_iva.xml` +
  `account_retention_islr.xml` (botón nuevo).
- No cambia el contrato de `account.retention.alert.wizard` ni el flujo cuando el usuario sí
  confirma manualmente (vía este botón nuevo o vía el flujo automático de
  `action_post`/`tfhka_auto_accept_sequence_mismatch`).
