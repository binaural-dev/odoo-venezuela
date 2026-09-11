# Fix: Coordinar la NC de donación con la nueva validación de origen de `l10n_ve_invoice`

## Why

Ticket Helpdesk #13965. `l10n_ve_invoice` incorpora un `@api.constrains` en
`account.move` que bloquea cualquier producto de una Nota de Crédito
(`out_refund`) ausente en la factura que revierte
(`reversed_entry_id`). `l10n_ve_donation._reverse_moves()`
(`models/account_move.py`) crea justamente ese tipo de NC, pero con un
producto de donación dedicado (`is_donation_product=True`), nunca el
producto de la factura original. Sin coordinación, revertir una factura de
donación se rompería con `ValidationError`.

## What Changes

- `_reverse_moves()` pasa ahora `l10n_ve_skip_refund_origin_validation=True`
  al `create()` de la Nota de Crédito de donación, el mismo mecanismo de
  bypass que ya usaba `l10n_ve_exchange_difference` de forma anticipada.
- Bump de manifest `19.0.2.0.2` -> `19.0.2.0.3`.

## Non-goals

- No cambia ninguna regla de negocio de donaciones, solo evita una
  regresión introducida por un módulo hermano.
