# Feat: botones para descargar los comprobantes de retención desde el documento

## Why

Ticket de helpdesk #15936: **"Agregar botones en la vista para descargar los
comprobantes de retención (IVA, ISLR y Municipal)"**.

En la vista del documento (`account.move`) ya existen botones de resumen que
abren las retenciones de cada tipo, pero no hay un acceso directo para descargar
el comprobante en PDF; el usuario debe imprimirlo desde el formulario de cada
retención o desde el menú Imprimir. El comprobante municipal solo puede
descargarse en PDF desde `municipal-retention-pdf-15877`.

## What Changes

- `l10n_ve_payment_extension/models/account_move.py`
  - Nuevo `action_download_retention_voucher`: toma el tipo del contexto
    (`retention_type`: `iva`, `islr` o `municipal`), busca las retenciones
    emitidas de ese tipo que incluyen el documento y devuelve la acción de
    `retention_voucher_action` sobre ellas. Con varias retenciones del mismo tipo
    el PDF trae un comprobante por cada una. Usa `report_action(config=False)`
    para que un administrador no vea el asistente de diseño de documentos.
  - Para las municipales fija `date_emision` si está vacío, igual que el botón
    del Excel, de modo que la fecha de entrega salga en el PDF.
- `l10n_ve_payment_extension/models/account_retention.py` y
  `views/account_retention_{iva,islr,municipal}.xml`
  - Nuevo `action_print_retention_voucher_pdf` y botón "Download voucher PDF" en
    el formulario de cada tipo de retención, visible solo con la retención
    emitida (`state == 'emitted'`). Para las municipales fija `date_emision` si
    está vacío, igual que el botón del Excel.
- `l10n_ve_payment_extension/views/account_move.xml`
  - Tres botones en la cabecera: "Download IVA voucher", "Download ISLR voucher"
    y "Download municipal voucher". Cada uno se muestra solo si el documento
    tiene una retención emitida de ese tipo.
- `l10n_ve_payment_extension/i18n/es_VE.po`
  - Traducciones de los botones y de los dos mensajes de error nuevos.

## Impact

- **Capability**: `retention-voucher-download-buttons` (nueva).
- **Módulo**: `l10n_ve_payment_extension`, versión `19.0.2.2.0`. Sin cambios de
  esquema ni de datos: no requiere migración.
- **Riesgo**: bajo. No sobrescribe métodos del ORM; el único efecto de escritura
  es `date_emision` en las municipales.
- **Decisión de alcance**: los botones se muestran cuando hay una retención
  *emitida* (no en borrador ni anulada), porque el PDF de un borrador está
  bloqueado. El ticket habla de "una retención de ese tipo"; si se quiere ver
  también en borrador, hay que revisar ese bloqueo.
- **Fuera de alcance**: el menú Imprimir no cambia.
