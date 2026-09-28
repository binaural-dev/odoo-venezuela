# Fix: bloquear montos calculados en retenciones IVA de proveedores

## Why

Ticket de helpdesk #15432: el formulario de retención de IVA
(`view_retention_iva_form_l10n_ve_payment_extension`) es compartido
entre retenciones de cliente y de proveedor -- lo usan tanto
`action_retention_iva_client` como `action_retention_iva_supplier`. Sus
campos de monto (`invoice_total`, `invoice_amount`, `iva_amount`,
`retention_amount`) eran editables a mano también para retenciones de
PROVEEDOR (`in_invoice`/`in_refund`/`in_debit`), pudiendo divergir del
monto real calculado desde la factura del proveedor -- algo que no debe
pasar de ese lado, porque esos montos deben reflejar exactamente lo que
dice la factura del proveedor, no un ajuste manual. Para retenciones de
CLIENTE (`out_invoice`/`out_refund`/`out_debit`) el ajuste manual sigue
siendo legítimo (el cliente puede declarar montos propios sobre su
propio comprobante).

## What Changes

- `l10n_ve_payment_extension/views/account_retention_iva.xml`
  - `invoice_total`, `invoice_amount`, `iva_amount` y
    `retention_amount`, dentro del list embebido de
    `retention_line_ids`, ahora son
    `readonly="parent.type in ('in_invoice', 'in_refund', 'in_debit')"`
    con `force_save="1"` -- de solo lectura (pero el valor sigue
    viajando en el guardado) cuando la retención es de proveedor. Para
    retenciones de cliente siguen editables como antes, sujeto solo a
    la regla de `state` ya existente.
  - Corrección de code review: mismo `readonly`/`force_save` agregado a
    sus 4 contrapartes "alternas" (`foreign_invoice_amount`,
    `foreign_iva_amount`, `foreign_invoice_total`,
    `foreign_retention_amount`), que quedaron sin el tratamiento
    inicialmente. Son los mismos montos en la moneda alterna, visibles
    cuando `base_currency_is_vef` es falso -- un `Boolean` con
    `default=` (no computed), por lo que una compañía secundaria en
    multi-compañía cuya moneda no sea VEF sí puede caer en esa rama.

## Impact

- **Capability**: `block-iva-supplier-retention-line-amounts` (nueva).
- **Módulo**: `l10n_ve_payment_extension`.
- **Riesgo**: bajo. Cambio puramente de vista (`readonly` +
  `force_save`); no toca el modelo ni el cálculo de los montos, que
  sigue viniendo del `onchange` sobre la factura
  (`_apply_iva_tax_group_values` en `account_retention_line.py`).
- **Verificado**: suite completa de `l10n_ve_payment_extension` (434
  tests) corrida en contenedor Docker sobre base limpia
  (`--without-demo=True`) - sin fallos, antes y después del cambio
  original, y de nuevo tras el fix de los campos `foreign_*`.
