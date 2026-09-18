# Fix: bloquear la Fecha de Comprobante anterior a la factura (además de la Fecha Contable)

## Why

Ticket de helpdesk #15188: **"Retención de IVA: Odoo permite registrar y
emitir la retención con Fecha Contable y de comprobante, anterior a la
Fecha de Factura"**.

`retention-accounting-date-validation` (helpdesk #15019/#14984, ver
`openspec/changes/retention-accounting-date-validation/`) ya bloqueaba
`date_accounting` anterior a la factura, tanto al guardar como al aprobar.
Pero esa validación solo comparaba `date_accounting` — dejaba `date`
(Fecha de Comprobante) completamente sin cubrir. Reproducido en staging: se
edita la retención generada, se cambia tanto `date_accounting` como `date`
a una fecha anterior a la factura (2 días antes), se guarda, y se presiona
"Aprobar" — Odoo lo permite sin ninguna advertencia, dejando la retención
`emitted` con `date` inconsistente con la factura que la origina.

## What Changes

- `l10n_ve_payment_extension/models/account_retention.py`
  - `_check_accounting_date_vs_invoices()`: además de la comparación
    existente contra `date_accounting`, agrega una segunda comparación
    contra `date` (Fecha de Comprobante) usando la misma
    `_get_max_invoice_date()` ya existente - mismo criterio (límite
    inclusivo, nombra la factura infractora), campo distinto.
  - `@api.constrains("date_accounting", "date", "retention_line_ids")
    _check_accounting_date()`: se agrega `date` a la lista de campos que
    disparan el constraint (antes solo `date_accounting`), para que editar
    únicamente `date` también dispare la validación al guardar.
  - `action_post()`: sin cambios en este punto - ya llamaba a
    `_check_accounting_date_vs_invoices()`, que ahora cubre ambos campos
    internamente.
- `l10n_ve_payment_extension/i18n/es_VE.po`
  - Nueva entrada de traducción para el mensaje de `date` anterior a la
    factura (mismo patrón que el de `date_accounting`, placeholders
    `%(voucher_date)s`, `%(invoice_date)s`, `%(invoice_name)s`).
- `l10n_ve_payment_extension/tests/test_retention_ti14548_rules.py`
  - `test_voucher_date_earlier_than_invoice_blocks_helpdesk_15188`: cubre
    `date` anterior a la factura (bloquea), `date_accounting` anterior a
    la factura (sigue bloqueando, sin regresión), y `date` igual a la
    factura (no bloquea, límite inclusivo).

## Impact

- **Capability**: `retention-accounting-date-validation` (existente,
  `MODIFIED`, no `ADDED` - extiende un requisito ya vigente en vez de
  agregar uno nuevo).
- **Módulo**: `l10n_ve_payment_extension`. Solo toca
  `_check_accounting_date_vs_invoices()` y el `@api.constrains` que ya
  existían para `date_accounting`; no se tocó `action_post()` ni
  `_get_max_invoice_date()`.
- **Alcance**: mismo alcance que la validación original - los tres tipos
  de retención (`iva`, `islr`, `municipal`) y ambos sentidos
  (`in_*`/`out_*`), porque comparten el mismo helper.
- **Riesgo**: bajo. Reutiliza exactamente el mismo patrón (mismo helper de
  fecha máxima, mismo tipo de excepción, mismo nombre de factura en el
  mensaje) que la validación de `date_accounting` ya probada en producción
  desde #15019/#14984 - solo agrega una segunda comparación con un campo
  distinto, sin cambiar la lógica de comparación en sí.
- **Retenciones ya emitidas** con `date` inconsistente con la factura (como
  la del ticket) no se corrigen con este cambio - es un fix hacia
  adelante, igual que #15019/#14984.
- **Relación con `_check_dates_not_in_future`**: existe una validación
  separada (helpdesk #14548, sin ticket propio) que bloquea que
  `date_accounting`/`date` sean **posteriores** a hoy. Junto con este
  cambio, ambas fechas quedan acotadas por los dos lados: ni futuras, ni
  anteriores a la factura que las origina.
- **Verificado**: `test_voucher_date_earlier_than_invoice_blocks_helpdesk_15188`
  corrido en contenedor Docker sobre una base de datos de prueba
  descartable; pasa con el fix. Suite completa del módulo verificada en
  aislado (329 tests, 0 fallos en el momento del commit).
