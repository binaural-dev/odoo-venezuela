# Fix: Validar la Nota de Crédito contra su factura origen al publicar, no al crear

## Why

Pruebas manuales de José Hernández (binaural-consultoria-sincronizacion-jh1)
y tarea 82707: sobre una factura que ya tiene una Nota de Crédito parcial
publicada, "Nota de Crédito" > "Revertir" rechaza la operación de inmediato
con *"El monto acreditado para el producto ... supera el monto facturado..."*
y no deja ningún borrador.

Desde Odoo 17 no existe el botón de reembolso parcial: el asistente copia la
factura completa en un borrador que el usuario debe reducir antes de
publicar. `_check_refund_against_origin` era un `@api.constrains`, así que se
ejecutaba en el `create()` de esa copia -- antes de que el usuario pudiera
editar nada -- y dejaba sin ninguna vía en la UI para emitir una segunda NC
sobre la misma factura.

## What Changes

- `_check_refund_against_origin` (`models/account_move.py`) deja de ser
  `@api.constrains` y se invoca desde `_post()`, sobre los movimientos en
  borrador, antes de `super()._post()`. Cubre `action_post`, el wizard de
  alerta de `l10n_ve_accountant`, "Revertir y crear factura" (`cancel=True`),
  la publicación automática y cualquier `_post()` de código.
- Se elimina `_check_refund_line_against_origin`
  (`models/account_move_line.py`): editar una línea de un borrador ya no se
  valida al momento, sino al publicar.
- Notas de Crédito hermanas que cuentan para el tope: antes "no canceladas"
  (incluía borradores); ahora **publicadas, o publicándose en la misma
  llamada a `_post()`**. Un borrador olvidado ya no bloquea publicar otra NC
  válida, y dos NC publicadas juntas siguen sumándose entre sí.
- Nuevo hook por registro `_l10n_ve_skip_refund_origin_validation()`: por
  defecto devuelve la clave de contexto `l10n_ve_skip_refund_origin_validation`.
  Permite que un módulo hijo exima sus NC por un campo guardado, necesario
  ahora que la validación corre en una llamada (la publicación) que puede
  ser distinta a la que creó la NC.
- Tests (`tests/test_refund_origin_validation.py`) adaptados para esperar el
  error al publicar. Nuevos casos: NC desde el asistente de reversión con una
  NC previa (borrador completo → reducir → publicar), borrador olvidado que
  no bloquea, dos NC publicadas juntas que exceden. El test de "línea sin
  producto" pasaba en realidad por `_check_product_id` de
  `l10n_ve_accountant` (constrains al crear); ahora quita el producto con un
  `write()` de línea y verifica el mensaje propio de esta validación.
- Bump de manifest `19.0.1.0.19` -> `19.0.1.0.20`.

## Módulos revisados por posible conflicto

Rastreado corriendo sus tests con la clave de contexto instrumentada:

- `l10n_ve_donation`: la clave moría en el `create()` de la NC; la NC queda
  en borrador (el `action_post()` de `l10n_ve_accountant` devuelve el wizard
  de alerta) y se publica después sin la clave. Pasa a eximirse por
  `is_donation` vía el hook (cambio propio en ese módulo).
- `l10n_ve_exchange_difference`: la clave llega viva hasta `_post()` tanto en
  la NC de diferencial como en la reversión de la ND. Sin cambios.
- `l10n_ve_igtf_note_debit`: la ND es `out_invoice` (no aplica). La NC que
  revierte la ND se publica sin la clave, pero pasa porque repite el
  producto de la ND sin exceder su monto. Sin cambios.

## Non-goals

- `account_invoice_pricelist` (OCA, `@api.depends("quantity")` en
  `_compute_price_unit`) reinicia el `price_unit` al precio de lista cuando
  se reduce la cantidad del borrador. Es ajeno a esta validación.
- El wizard de alerta sobre la factura de donación ya publicada ("Aceptar"
  daría "must be in draft"). Ajeno a este cambio.
