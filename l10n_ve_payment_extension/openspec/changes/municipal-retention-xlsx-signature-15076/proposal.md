# Fix: firma no se inserta en el Excel de retención municipal

## Why

Ticket de helpdesk #15076: **"No se puede descargar el reporte de
retención municipal cuando tiene firma configurada"**.

El reporte XLSX de retención municipal
(`municipal.retention.xlsx.xlsx_file()`) llamaba a
`tools.image_process(...)`, importando `tools` desde `odoo` (`from odoo
import models, tools`). En esta versión de Odoo, `image_process` ya no
está re-exportado en el paquete `odoo.tools` (vive únicamente en el
submódulo `odoo.tools.image`, tal como lo usa el propio core en
`addons/base/models/ir_binary.py`). Cuando la compañía tenía una firma
activa configurada (`signature.config`), la descarga fallaba con
`AttributeError: module 'odoo.tools' has no attribute 'image_process'`,
devolviendo un error interno 500 al usuario sin entregar ningún archivo.

## What Changes

- `l10n_ve_payment_extension/report/municipal_retention_xlsx.py`
  - Import: `from odoo.tools.image import image_process` en vez de
    `from odoo import models, tools`.
  - Llamada: `image_process(...)` en vez de `tools.image_process(...)`.
- `l10n_ve_payment_extension/tests/test_municipal_retention_xlsx_report.py`
  (nuevo)
  - Dos regresiones: descarga con firma activa configurada (el caso del
    bug) y sin firma configurada (caso sano). Ambas verifican que el
    archivo devuelto sea un XLSX válido (encabezado `b"PK"`).

## Impact

- **Capability**: `municipal-retention-xlsx-signature` (nueva).
- **Módulo**: `l10n_ve_payment_extension`. Cambio de un import y una
  llamada; no toca el layout ni el contenido del reporte.
- **Riesgo**: bajo. Reemplaza un import roto por el correcto sin cambiar
  ningún comportamiento de negocio.
- **Verificado**: corrido en contenedor Docker sobre una base de datos
  limpia (instalada desde cero, sin datos de prueba previos). Confirmado
  que el test falla con el `AttributeError` original sobre el código sin
  el fix, y pasa con el fix aplicado. Suite completa del módulo corrida
  en aislado: sin fallos.
