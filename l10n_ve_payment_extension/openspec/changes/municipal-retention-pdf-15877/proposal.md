# Feat: comprobante de retención municipal en PDF

## Why

Ticket de helpdesk #15877: **"Falta el formato de PDF propio para el
comprobante de retención municipal (actividades económicas)"**.

El comprobante de retención municipal solo podía imprimirse en Excel
(`municipal.retention.xlsx`). Al imprimir el PDF (`retention_voucher_action`),
`_get_report_values` lanzaba un `ValidationError` ("Las retenciones municipales
no tienen recibo PDF. Por favor imprima el excel"). Sin ese bloqueo, el
despachador `retention_voucher_template` solo distinguía `iva` y enviaba
cualquier otro tipo al formato de ISLR.

## What Changes

- `l10n_ve_payment_extension/report/retention_voucher_report.py`
  - Se elimina el bloqueo de retenciones municipales.
  - Nuevo `_get_municipal_retention_data`, expuesto al template como
    `municipal_data` (un dict por retención municipal). Reutiliza las mismas
    fuentes que el Excel: `municipal.retention.xlsx._get_tax_authorities_record`
    para la cabecera y `get_xlsx_municipal_retention` para las filas, de modo
    que el PDF y el Excel muestran siempre los mismos datos y el override de
    subsidiarias (`binaural_subsidiary_payment_extension`) sigue aplicando.
  - El formato de montos y alícuota se decide por nombre de columna, no por
    posición.
- `l10n_ve_payment_extension/report/retention_voucher_templates.xml`
  - Nuevo template `report_municipal_customer` con el contenido del Excel
    en formato vertical, y rama `municipal` en `retention_voucher_template`.
  - La grilla se arma con tablas: `wkhtmltopdf` no soporta flexbox y las
    clases de Bootstrap no se aplican dentro de `web.basic_layout`.
- `l10n_ve_payment_extension/report/retention_voucher_reports.xml` y
  `models/ir_actions_report.py`
  - Nuevo paperformat A4 vertical (`paper_format_retention_municipal_voucher`),
    aplicado vía `get_paperformat` solo cuando todas las retenciones del lote
    son municipales.
- `l10n_ve_payment_extension/tests/test_municipal_retention_pdf.py` (nuevo)
  - Siete pruebas: render, lote mixto IVA y municipal, cabecera, fecha de
    entrega oculta, `date_emision` vacío, borrador bloqueado y filas iguales
    al Excel.
- `l10n_ve_payment_extension/tests/test_retention_lifecycle.py`
  - `test_15` fija `invoice_date` e `invoice_date_display` al mismo día: el
    guard de `l10n_ve_invoice` (ti-15450) rechaza una fecha de tasa posterior
    a la fecha de la factura.

## Impact

- **Capability**: `municipal-retention-pdf` (nueva).
- **Módulo**: `l10n_ve_payment_extension`, versión `19.0.2.1.0`. No hay
  cambios de esquema ni de datos: no requiere migración.
- **Excel**: sin cambios; sigue disponible con su botón.
- **IVA e ISLR**: sin cambios de formato ni de papel.
- **Riesgo**: bajo. Quita un bloqueo y agrega un template; el único código
  compartido es `get_paperformat`, que devuelve el comportamiento original
  salvo para lotes municipales.
- **Decisión abierta**: el logo usa el de la compañía y, si falta, el de la
  autoridad tributaria (`tax_authorities_logo`); el Excel usa solo este
  último.
