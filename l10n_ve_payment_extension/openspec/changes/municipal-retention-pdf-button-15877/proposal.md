# Feat: botón para descargar el PDF de la retención municipal

## Why

Seguimiento del ticket de helpdesk #15877 ("Falta el formato de PDF propio
para el comprobante de retención municipal"). El PDF ya existe
(`municipal-retention-pdf-15877`), pero solo se imprime desde Imprimir →
Retention Voucher, mientras que el Excel tiene su propio botón en la cabecera
del formulario. Se agrega el botón equivalente para el PDF.

## What Changes

- `l10n_ve_payment_extension/models/account_retention.py`
  - Nuevo `action_print_municipal_retention_pdf`: como el del Excel, fija
    `date_emision` en la primera impresión (así la fecha de entrega sale en el
    PDF) y devuelve la acción de `retention_voucher_action`.
- `l10n_ve_payment_extension/views/account_retention_municipal.xml`
  - Botón "Print municipal retention PDF" junto al del Excel, oculto en
    borrador.
- `l10n_ve_payment_extension/i18n/es_VE.po`
  - Traducción al español del texto del botón.

## Impact

- **Capability**: `municipal-retention-pdf-button` (nueva).
- **Módulo**: `l10n_ve_payment_extension`. Sin cambios de esquema ni de datos:
  no requiere migración.
- **Riesgo**: bajo. El método no sobrescribe ningún método del ORM; el único
  efecto de escritura es `date_emision`, igual que el botón del Excel.
- **Fuera de alcance**: el Excel, el template del PDF y el menú Imprimir.
