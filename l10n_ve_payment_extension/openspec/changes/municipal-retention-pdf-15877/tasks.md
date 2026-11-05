# Tasks

## 1. Diagnóstico

- [x] 1.1 Reproducido: imprimir el PDF de una retención municipal emitida
      lanza `ValidationError`
- [x] 1.2 Identificado el bloqueo en `retention_voucher_report.py` y el
      despachador `retention_voucher_template`, que enviaría todo lo que no es
      IVA al formato de ISLR

## 2. Implementación

- [x] 2.1 Eliminado el bloqueo de retenciones municipales
- [x] 2.2 Helper `_get_municipal_retention_data` sobre las fuentes del Excel
- [x] 2.3 Template `report_municipal_customer` y rama `municipal` en el
      despachador
- [x] 2.4 Paperformat A4 vertical aplicado solo a lotes municipales
- [x] 2.5 Formato por nombre de columna (revisión del PR #1477)

## 3. Verificación

- [x] 3.1 Siete pruebas en `test_municipal_retention_pdf.py`
- [x] 3.2 `test_15_accounting_date_multi_invoice_uses_latest_date` ajustado al
      guard de ti-15450
- [x] 3.3 Suite del módulo corrida por el CI del PR #1477: sin fallos
- [x] 3.4 Validado por funcional en el staging de vertical-contabilidad-2
- [ ] 3.5 Prueba de `get_paperformat` (papel vertical para municipales,
      horizontal para el resto): sin cobertura hoy

## 4. OpenSpec

- [x] 4.1 `proposal.md` + spec delta (`ADDED`: capability nueva)
- [ ] 4.2 `openspec validate --changes` (no ejecutado: CLI `openspec` no
      disponible en este entorno)

## 5. Proceso

- [x] 5.1 Rama `maint-19.0-feat-ti-15877-pdf-retencion-municipal`, PR #1477
- [ ] 5.2 Merge a `maintenance-19.0`
