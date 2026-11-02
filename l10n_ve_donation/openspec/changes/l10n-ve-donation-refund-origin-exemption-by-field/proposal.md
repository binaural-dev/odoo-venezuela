# Fix: Eximir la NC de donación de la validación de origen por `is_donation`

## Why

`l10n_ve_invoice` ahora valida la Nota de Crédito contra su factura origen
al **publicar** (`_post()`), no al crear (ver
`l10n_ve_invoice/openspec/changes/l10n-ve-invoice-refund-origin-validation-on-post`).
La NC de donación se creaba con la clave de contexto
`l10n_ve_skip_refund_origin_validation` en `_reverse_moves()`, pero esa
clave muere con el `create()`: la NC queda en borrador (el `action_post()`
de `l10n_ve_accountant` devuelve el wizard de alerta en vez de publicar) y
se publica después, a mano, sin la clave. Con la validación en `_post()`
esa publicación quedaría bloqueada, porque el producto de donación nunca
está en la factura original.

## What Changes

- Override de `_l10n_ve_skip_refund_origin_validation()` en `account.move`
  (`models/account_move.py`): devuelve `is_donation` o el resultado del
  padre. La exención queda ligada a un campo guardado, no al contexto.
- La clave de contexto en el `create()` de `_reverse_moves()` se mantiene,
  documentada como redundante.
- Tests (`tests/test_donation_credit_note_regression.py`):
  - `test_regression_without_bypass_would_block_the_reversal` se reemplaza
    por `test_is_donation_exempts_credit_note_from_origin_validation`. El
    test anterior fallaba por la razón equivocada: sumaba como hermana la
    NC automática en borrador (el producto de donación es Servicio y solo
    compite contra el total). El nuevo usa un monto que excede el total por
    sí solo, y compara `is_donation=False` (bloqueada) contra
    `is_donation=True` (publicada).
  - Nuevo `test_donation_credit_note_posted_later_without_context_key`: la
    NC automática queda en borrador y se publica con `_post()` sin la clave.
- Bump de manifest `19.0.2.0.4` -> `19.0.2.0.5`.

## Non-goals

- Que la NC de donación se publique sola (hoy queda en borrador por el
  wizard de alerta) y el error "must be in draft" al pulsar "Aceptar" en la
  alerta de la factura ya publicada: comportamiento previo, fuera de este
  cambio. Sí se corrige el spec consolidado
  (`openspec/specs/l10n_ve_donation/spec.md`), que decía "se crea y publica
  automáticamente" y ahora describe que la NC queda en borrador.
